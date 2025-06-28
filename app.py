import os
import datetime
import requests
import uuid
import qrcode
from io import BytesIO
import base64
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from models import db, User, Condominio, Product, Inventory, Sale
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from PIL import Image
import secrets
from datetime import timedelta
from sqlalchemy import func

# --- Configuração da Aplicação ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'geladeira.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/profile_pics')

# --- CONFIGURAÇÃO DO MERCADO PAGO ---
# ATENÇÃO: Substitua pelas suas chaves reais de PRODUÇÃO do Mercado Pago
MERCADO_PAGO_ACCESS_TOKEN = 'APP_USR-2683965692592409-071011-19820758846ee46db59f8bb79039b115-250701524'
MERCADO_PAGO_API_URL = 'https://api.mercadopago.com/v1/payments'
MERCADO_PAGO_PREFERENCES_URL = 'https://api.mercadopago.com/checkout/preferences'

db.init_app(app)

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, inicie a sessão para aceder a esta página."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Funções Auxiliares ---
def is_cpf_valid(cpf: str) -> bool:
    cpf_digits = [int(digit) for digit in cpf if digit.isdigit()]
    if len(cpf_digits) != 11 or len(set(cpf_digits)) == 1:
        return False

    # Validação do primeiro dígito verificador
    sum_of_products = sum(a*b for a, b in zip(cpf_digits[0:9], range(10, 1, -1)))
    expected_digit = (sum_of_products * 10 % 11) % 10
    if cpf_digits[9] != expected_digit:
        return False

    # Validação do segundo dígito verificador
    sum_of_products = sum(a*b for a, b in zip(cpf_digits[0:10], range(11, 1, -1)))
    expected_digit = (sum_of_products * 10 % 11) % 10
    if cpf_digits[10] != expected_digit:
        return False

    return True

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'user_dashboard'))
    if request.method == 'POST':
        cpf = request.form.get('cpf')
        password = request.form.get('password')
        user = User.query.filter_by(cpf=cpf).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('admin_dashboard' if user.is_admin else 'user_dashboard'))
        else:
            flash('CPF ou palavra-passe incorretos. Tente novamente.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('cart', None)
    flash('Sessão terminada com sucesso.', 'success')
    return redirect(url_for('login'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        cpf = request.form.get('cpf')
        birth_date = request.form.get('birth_date')
        password = request.form.get('password')
        condominio_name = request.form.get('condominio_name')
        apartment_address = request.form.get('apartment_address')
        
        # 1. Validação Matemática Obrigatória
        if not is_cpf_valid(cpf):
            flash('O formato do CPF informado é inválido. Por favor, verifique.', 'danger')
            return redirect(url_for('cadastro'))

        # 2. Tentativa de Validação na API (não bloqueia mais o utilizador)
        try:
            cpf_limpo = ''.join(filter(str.isdigit, cpf))
            api_url = f"https://brasilapi.com.br/api/cpf/v1/{cpf_limpo}"
            response = requests.get(api_url, timeout=5) # Adiciona um timeout de 5 segundos
            
            if response.status_code == 200:
                data = response.json()
                if data.get('situacao') != 'REGULAR':
                    flash(f"O CPF informado está com a situação '{data.get('situacao', 'desconhecida')}' na Receita Federal.", 'danger')
                    return redirect(url_for('cadastro'))
            else:
                print(f"AVISO: Não foi possível validar o estado do CPF {cpf}. API retornou status {response.status_code}. A continuar com o registo.")

        except requests.exceptions.RequestException as e:
            print(f"AVISO: A API de validação de CPF está offline ou demorou a responder. Erro: {e}. A continuar com o registo.")

        # 3. Verifica se o CPF já existe no seu sistema
        if User.query.filter_by(cpf=cpf).first():
            flash('Este CPF já foi registado.', 'error')
            return redirect(url_for('cadastro'))
            
        # 4. Se tudo estiver bem, cria o utilizador
        new_user = User(full_name=full_name, cpf=cpf, birth_date=birth_date, condominio_name=condominio_name, apartment_address=apartment_address)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registo efetuado com sucesso! Inicie a sessão.', 'success')
        return redirect(url_for('registro_sucesso'))
        
    condominios_disponiveis = Condominio.query.order_by(Condominio.name).all()
    return render_template('cadastro.html', condominios=condominios_disponiveis)

# --- ROTAS DO PAINEL DO UTILIZADOR ---
@app.route('/')
@app.route('/dashboard')
@login_required
def user_dashboard():
    if current_user.is_admin: return redirect(url_for('admin_dashboard'))
    condo = Condominio.query.filter_by(name=current_user.condominio_name).first()
    products_in_condo = []
    if condo:
        products_in_condo = Inventory.query.filter_by(condominio_id=condo.id).filter(Inventory.quantity > 0).all()
    todos_condominios = Condominio.query.order_by(Condominio.name).all()
    favorite_ids = {fav.id for fav in current_user.favorite_products}
    return render_template('user_dashboard.html', 
                           products_in_condo=products_in_condo, 
                           todos_condominios=todos_condominios,
                           favorite_ids=favorite_ids)

# --- ROTAS DE GESTÃO DO UTILIZADOR ---
@app.route('/meu_perfil', methods=['GET', 'POST'])
@login_required
def meu_perfil():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            current_user.full_name = request.form.get('full_name')
            current_user.apartment_address = request.form.get('apartment_address')
            
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file.filename != '':
                    picture_file = save_picture(file)
                    current_user.profile_image = picture_file
            
            db.session.commit()
            flash('Os seus dados foram atualizados com sucesso!', 'success')

        elif action == 'change_password':
            old_password = request.form.get('old_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not current_user.check_password(old_password):
                flash('A sua palavra-passe antiga está incorreta.', 'danger')
            elif new_password != confirm_password:
                flash('As novas palavras-passe não coincidem.', 'danger')
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash('Palavra-passe alterada com sucesso!', 'success')
        
        return redirect(url_for('meu_perfil'))

    return render_template('meu_perfil.html')


# --- NOVA ROTA PARA EXCLUIR CONTA ---
@app.route('/excluir_minha_conta', methods=['POST'])
@login_required
def excluir_minha_conta():
    user = User.query.get(current_user.id)
    if user:
        Sale.query.filter_by(user_id=user.id).delete()
        user.favorite_products = []
        db.session.commit()
        
        db.session.delete(user)
        db.session.commit()
        
        logout_user()
        flash('A sua conta foi excluída com sucesso.', 'success')
        return redirect(url_for('login'))
    
    flash('Ocorreu um erro ao excluir a sua conta.', 'danger')
    return redirect(url_for('meu_perfil'))

# --- NOVA ROTA DEDICADA AO UPLOAD DA FOTO ---
@app.route('/upload_profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file.filename != '':
            try:
                picture_file = save_picture(file)
                current_user.profile_image = picture_file
                db.session.commit()
                flash('Foto de perfil atualizada com sucesso!', 'success')
            except Exception as e:
                flash('Ocorreu um erro ao guardar a sua foto.', 'danger')
                print(e)
    return redirect(url_for('meu_perfil'))

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.config['UPLOAD_FOLDER'], picture_fn)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    i = Image.open(form_picture)
    i.thumbnail((250, 250)) # Aumentei um pouco a qualidade
    i.save(picture_path)
    return picture_fn

@app.route('/toggle_favorite/<int:product_id>', methods=['POST'])
@login_required
def toggle_favorite(product_id):
    produto = Product.query.get_or_404(product_id)
    if produto in current_user.favorite_products: current_user.favorite_products.remove(produto)
    else: current_user.favorite_products.append(produto)
    db.session.commit(); return jsonify({'status': 'ok'})

@app.route('/update_my_condo', methods=['POST'])
@login_required
def update_my_condo():
    novo_condominio = request.form.get('new_condo_name')
    if novo_condominio:
        utilizador = User.query.get(current_user.id); utilizador.condominio_name = novo_condominio
        session.pop('cart', None)
        db.session.commit(); flash('O seu condomínio foi alterado com sucesso! A loja foi atualizada.', 'success')
    return redirect(url_for('user_dashboard'))

# --- ROTAS DO CARRINHO E CHECKOUT ---
@app.route('/adicionar_carrinho/<int:inventory_id>', methods=['POST'])
@login_required
def adicionar_carrinho(inventory_id):
    cart = session.get('cart', {}); item_id_str = str(inventory_id)
    item = Inventory.query.get_or_404(inventory_id)
    current_quantity_in_cart = cart.get(item_id_str, 0)
    if current_quantity_in_cart >= item.quantity: return jsonify({'status': 'error', 'message': 'Stock insuficiente!'})
    cart[item_id_str] = cart.get(item_id_str, 0) + 1
    session['cart'] = cart
    return jsonify({'status': 'ok', 'cart_item_count': len(cart)})

@app.route('/carrinho')
@login_required
def ver_carrinho():
    cart = session.get('cart', {})
    cart_items = []
    total_geral = 0
    if cart:
        for inv_id, quantity in cart.items():
            item = Inventory.query.get(int(inv_id))
            if item:
                subtotal = item.product.sell_price * quantity
                # CORREÇÃO: Renomeado 'item' para 'inventory_item' para evitar conflitos
                cart_items.append({'inventory_item': item, 'quantity': quantity, 'subtotal': subtotal})
                total_geral += subtotal
    return render_template('carrinho.html', cart_items=cart_items, total_geral=total_geral)

@app.route('/atualizar_carrinho', methods=['POST'])
@login_required
def atualizar_carrinho():
    cart = session.get('cart', {}); inv_id_str = request.form.get('inventory_id'); quantity = int(request.form.get('quantity'))
    item = Inventory.query.get_or_404(int(inv_id_str))
    if 0 < quantity <= item.quantity: cart[inv_id_str] = quantity
    elif quantity <= 0: cart.pop(inv_id_str, None)
    else: flash('Quantidade inválida ou superior ao stock.', 'danger')
    session['cart'] = cart
    return redirect(url_for('ver_carrinho'))

@app.route('/remover_do_carrinho', methods=['POST'])
@login_required
def remover_do_carrinho():
    cart = session.get('cart', {}); inv_id_str = request.form.get('inventory_id')
    if inv_id_str in cart: cart.pop(inv_id_str, None)
    session['cart'] = cart
    return redirect(url_for('ver_carrinho'))

# --- NOVA ROTA PARA LIMPAR O CARRINHO ---
@app.route('/limpar_carrinho', methods=['POST'])
@login_required
def limpar_carrinho():
    session.pop('cart', None)
    flash('O seu carrinho foi esvaziado.', 'success')
    return redirect(url_for('ver_carrinho'))


@app.route('/finalizar_compra_pix')
@login_required
def finalizar_compra_pix():
    cart = session.get('cart', {});
    if not cart: return redirect(url_for('user_dashboard'))
    total_amount = 0; description_items = []; order_id = str(uuid.uuid4())
    for inv_id, quantity in cart.items():
        item = Inventory.query.get(int(inv_id));
        if not item or item.quantity < quantity:
            flash(f"Stock insuficiente para {item.product.name}. Por favor, ajuste o seu carrinho.", "danger"); return redirect(url_for('ver_carrinho'))
        total_amount += item.product.sell_price * quantity
        description_items.append(f"{quantity}x {item.product.name}")
        nova_venda = Sale(user_id=current_user.id, product_id=item.product.id, condominio_id=item.condominio_id, quantity_sold=quantity, price_at_sale=item.product.sell_price * quantity, cost_at_sale=item.product.cost_price * quantity, status='pending', payment_id=order_id)
        db.session.add(nova_venda)
    db.session.commit()
    total_amount = round(total_amount, 2); description = ", ".join(description_items)
    
    headers = {'Authorization': f'Bearer {MERCADO_PAGO_ACCESS_TOKEN}', 'Content-Type': 'application/json', 'X-Idempotency-Key': order_id}
    notification_url = url_for('webhook_mercado_pago', _external=True)
    payload = {"transaction_amount": float(total_amount), "description": description, "payment_method_id": "pix", "payer": {"email": f"cliente_{current_user.id}@smartbox.com"}, "external_reference": order_id}
    try:
        response = requests.post(MERCADO_PAGO_API_URL, json=payload, headers=headers); response.raise_for_status()
        payment_data = response.json(); sale_payment_id = str(payment_data['id'])
        Sale.query.filter_by(payment_id=order_id).update({"payment_id": sale_payment_id}); db.session.commit()
        qr_code = payment_data['point_of_interaction']['transaction_data']['qr_code']; qr_code_base64 = payment_data['point_of_interaction']['transaction_data']['qr_code_base64']
        return render_template('payment.html', qr_code=qr_code, qr_code_base64=qr_code_base64, sale_payment_id=sale_payment_id)
    except requests.exceptions.RequestException as e:
        print(f"Erro ao comunicar com o Mercado Pago: {e}"); flash('Não foi possível iniciar o pagamento PIX.', 'error'); return redirect(url_for('ver_carrinho'))

@app.route('/webhook/pix', methods=['POST'])
def webhook_mercado_pago():
    data = request.json
    if data and data.get('type') == 'payment':
        payment_id = str(data['data']['id'])
        response = requests.get(f'{MERCADO_PAGO_API_URL}/{payment_id}', headers={'Authorization': f'Bearer {MERCADO_PAGO_ACCESS_TOKEN}'})
        if response.ok:
            payment_info = response.json(); order_id = payment_info.get('external_reference')
            if payment_info.get('status') == 'approved':
                vendas = Sale.query.filter_by(payment_id=order_id).all()
                if vendas and vendas[0].status == 'pending':
                    for venda in vendas:
                        venda.status = 'paid'; venda.payment_id = payment_id
                        item = Inventory.query.filter_by(condominio_id=venda.condominio_id, product_id=venda.product_id).first()
                        if item: item.quantity -= venda.quantity_sold
                    db.session.commit(); print(f"PAGAMENTO APROVADO VIA WEBHOOK! Ordem ID: {order_id}.")
    return jsonify({"status": "ok"}), 200

# --- ROTA DE VERIFICAÇÃO DE PAGAMENTO (NOVA LÓGICA) ---
@app.route('/check_payment_status/<string:sale_payment_id>')
@login_required
def check_payment_status(sale_payment_id):
    venda = Sale.query.filter_by(payment_id=sale_payment_id).first()

    # Se a venda ainda estiver pendente, vamos verificar no Mercado Pago
    if venda and venda.status == 'pending':
        try:
            response = requests.get(
                f'{MERCADO_PAGO_API_URL}/{sale_payment_id}',
                headers={'Authorization': f'Bearer {MERCADO_PAGO_ACCESS_TOKEN}'}
            )
            response.raise_for_status()
            payment_info = response.json()

            # Se o Mercado Pago confirmar que o pagamento foi aprovado
            if payment_info.get('status') == 'approved':
                order_id = payment_info.get('external_reference')
                vendas_da_ordem = Sale.query.filter_by(payment_id=order_id, status='pending').all()

                for v in vendas_da_ordem:
                    v.status = 'paid'
                    v.payment_id = sale_payment_id # Atualiza com o ID de pagamento final

                    # --- LINHAS ADICIONADAS PARA DESCONTAR O STOCK ---
                    item_no_inventario = Inventory.query.filter_by(product_id=v.product_id, condominio_id=v.condominio_id).first()
                    if item_no_inventario:
                        item_no_inventario.quantity -= v.quantity_sold
                    # --- FIM DAS LINHAS ADICIONADAS ---

                db.session.commit()
                return jsonify({"status": "paid", "order_id": order_id})

        except requests.exceptions.RequestException as e:
            print(f"Erro ao verificar o estado do pagamento: {e}")
            return jsonify({"status": "error"})

    # Se a venda já estava paga na nossa base de dados
    elif venda and venda.status == 'paid':
        return jsonify({"status": "paid", "order_id": venda.payment_id})

    # Se não encontrou ou ainda está pendente após a verificação
    return jsonify({"status": "pending"})

@app.route('/pagamento_aprovado/<string:order_id>')
@login_required
def pagamento_aprovado(order_id):
    # Gera o QR Code com o order_id para ser lido pela geladeira
    qr = qrcode.QRCode(version=1, box_size=10, border=5); qr.add_data(order_id); qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white'); buffered = BytesIO()
    img.save(buffered, format="PNG"); img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    qr_code_url = f"data:image/png;base64,{img_str}"
    session.pop('cart', None) # Limpa o carrinho
    return render_template('payment_success.html', qr_code_url=qr_code_url)

@app.route('/payment_failed')
@login_required
def payment_failed():
    return render_template('payment_failed.html')

# --- ROTA PARA O HARDWARE DA GELADEIRA ---
@app.route('/api/liberar_geladeira/<string:order_id>')
def api_liberar_geladeira(order_id):
    venda = Sale.query.filter_by(payment_id=order_id, status='paid').first()
    if venda:
        print(f"Comando recebido: ABRIR GELADEIRA para a ordem {order_id}"); return jsonify({"status": "success", "message": "Porta liberada"}), 200
    else:
        print(f"Tentativa de abertura FALHOU para a ordem {order_id}"); return jsonify({"status": "error", "message": "QR Code inválido ou não pago"}), 404

# --- ROTAS DO PAINEL DO ADMINISTRADOR ---
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    return redirect(url_for('gerenciar_condominios'))

@app.route('/admin/condominios', methods=['GET', 'POST'])
@login_required
def gerenciar_condominios():
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    if request.method == 'POST':
        condo_name = request.form.get('condo_name'); responsible_name = request.form.get('responsible_name')
        if Condominio.query.filter_by(name=condo_name).first(): flash('Já existe um condomínio com este nome.', 'error')
        else:
            new_condo = Condominio(name=condo_name, responsible_name=responsible_name); db.session.add(new_condo); db.session.commit()
            flash('Condomínio adicionado com sucesso!', 'success')
        return redirect(url_for('gerenciar_condominios'))
    todos_condominios = Condominio.query.order_by(Condominio.name).all()
    return render_template('gerenciar_condominios.html', condominios=todos_condominios)

@app.route('/admin/condominios/excluir/<int:condo_id>', methods=['POST'])
@login_required
def excluir_condominio(condo_id):
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    condo_para_excluir = Condominio.query.get_or_404(condo_id)
    Inventory.query.filter_by(condominio_id=condo_id).delete(); Sale.query.filter_by(condominio_id=condo_id).delete()
    User.query.filter_by(condominio_name=condo_para_excluir.name).update({"condominio_name": "N/A (Condomínio Removido)"})
    db.session.delete(condo_para_excluir); db.session.commit()
    flash(f'Condomínio "{condo_para_excluir.name}" e todos os seus dados foram excluídos com sucesso.', 'success')
    return redirect(url_for('gerenciar_condominios'))

@app.route('/admin/utilizadores', methods=['GET', 'POST'])
@login_required
def gerenciar_utilizadores():
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    query = User.query.filter_by(is_admin=False)
    if request.method == 'POST':
        search_query = request.form.get('search')
        if search_query: query = query.filter(User.full_name.ilike(f'%{search_query}%'))
    utilizadores = query.order_by(User.full_name).all()
    return render_template('gerenciar_utilizadores.html', utilizadores=utilizadores)

@app.route('/admin/utilizadores/alterar_senha/<int:user_id>', methods=['POST'])
@login_required
def alterar_senha_utilizador(user_id):
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    user = User.query.get_or_404(user_id)
    nova_senha = request.form.get('new_password')
    if not nova_senha: flash('Nenhuma palavra-passe fornecida.', 'danger')
    else:
        user.set_password(nova_senha); db.session.commit()
        flash(f'Palavra-passe do utilizador {user.full_name} alterada com sucesso.', 'success')
    return redirect(url_for('gerenciar_utilizadores'))

@app.route('/admin/utilizadores/excluir/<int:user_id>', methods=['POST'])
@login_required
def excluir_utilizador(user_id):
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    user_para_excluir = User.query.get_or_404(user_id)
    if user_para_excluir.is_admin:
        flash('Não é possível excluir um utilizador administrador.', 'danger'); return redirect(url_for('gerenciar_utilizadores'))
    Sale.query.filter_by(user_id=user_id).delete()
    user_para_excluir.favorite_products = []
    db.session.delete(user_para_excluir); db.session.commit()
    flash(f'Utilizador {user_para_excluir.full_name} e todos os seus dados foram excluídos.', 'success')
    return redirect(url_for('gerenciar_utilizadores'))

@app.route('/admin/geladeiras')
@login_required
def selecionar_geladeira():
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    condominios = Condominio.query.order_by(Condominio.name).all()
    return render_template('selecionar_geladeira.html', condominios=condominios)

@app.route('/admin/geladeira/<int:condo_id>', methods=['GET', 'POST'])
@login_required
def gerir_geladeira(condo_id):
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    condo = Condominio.query.get_or_404(condo_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_from_catalog':
            product_id = request.form.get('product_id'); quantity = request.form.get('quantity')
            if not product_id or not quantity or int(quantity) < 0: flash('Selecione um produto e uma quantidade válida.', 'error')
            else:
                existing_item = Inventory.query.filter_by(condominio_id=condo_id, product_id=product_id).first()
                if existing_item:
                    existing_item.quantity += int(quantity); flash(f'Stock de "{existing_item.product.name}" reabastecido.', 'success')
                else:
                    new_item = Inventory(condominio_id=condo_id, product_id=product_id, quantity=int(quantity)); db.session.add(new_item); flash('Produto adicionado ao inventário da geladeira.', 'success')
                db.session.commit()
        elif action == 'remove_item':
            inventory_id = request.form.get('inventory_id'); item_to_remove = Inventory.query.get(inventory_id)
            if item_to_remove: flash(f'Produto "{item_to_remove.product.name}" removido da geladeira.', 'success'); db.session.delete(item_to_remove); db.session.commit()
        elif action == 'update_quantity':
            inventory_id = request.form.get('inventory_id'); new_quantity = request.form.get('new_quantity')
            if new_quantity and int(new_quantity) >= 0:
                item_to_update = Inventory.query.get(inventory_id)
                if item_to_update: item_to_update.quantity = int(new_quantity); flash(f'Stock de "{item_to_update.product.name}" atualizado.', 'success'); db.session.commit()
        return redirect(url_for('gerir_geladeira', condo_id=condo_id))
    inventory_items = Inventory.query.filter_by(condominio_id=condo_id).all()
    all_products = Product.query.order_by(Product.name).all()
    return render_template('gerir_geladeira.html', condo=condo, inventory_items=inventory_items, all_products=all_products)

@app.route('/admin/catalogo', methods=['GET', 'POST'])
@login_required
def gerenciar_catalogo():
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    if request.method == 'POST':
        name = request.form.get('product_name'); cost_price = request.form.get('cost_price'); sell_price = request.form.get('sell_price'); image_url = request.form.get('image_url')
        if Product.query.filter_by(name=name).first():
            flash('Já existe um produto com este nome no catálogo.', 'error')
        else:
            new_product = Product(name=name, cost_price=float(cost_price), sell_price=float(sell_price), image_url=image_url); db.session.add(new_product); db.session.commit(); flash('Produto adicionado ao catálogo com sucesso!', 'success')
        return redirect(url_for('gerenciar_catalogo'))
    todos_produtos = Product.query.order_by(Product.name).all()
    return render_template('gerenciar_catalogo.html', produtos=todos_produtos)

@app.route('/admin/catalogo/excluir/<int:product_id>', methods=['POST'])
@login_required
def excluir_produto_catalogo(product_id):
    if not current_user.is_admin: return redirect(url_for('user_dashboard'))
    produto_para_excluir = Product.query.get_or_404(product_id)
    Inventory.query.filter_by(product_id=product_id).delete(); Sale.query.filter_by(product_id=product_id).delete()
    db.session.delete(produto_para_excluir); db.session.commit()
    flash(f'Produto "{produto_para_excluir.name}" foi excluído do catálogo global.', 'success')
    return redirect(url_for('gerenciar_catalogo'))

def is_cpf_valid(cpf: str) -> bool:
    cpf_digits = [int(digit) for digit in cpf if digit.isdigit()]
    if len(cpf_digits) != 11 or len(set(cpf_digits)) == 1: return False
    sum_of_products = sum(a*b for a, b in zip(cpf_digits[0:9], range(10, 1, -1)))
    expected_digit = (sum_of_products * 10 % 11) % 10
    if cpf_digits[9] != expected_digit: return False
    sum_of_products = sum(a*b for a, b in zip(cpf_digits[0:10], range(11, 1, -1)))
    expected_digit = (sum_of_products * 10 % 11) % 10
    if cpf_digits[10] != expected_digit: return False
    return True

@app.route('/api/validate_cpf/<string:cpf>')
def validate_cpf_api(cpf):
    cpf_formatado = ''.join(filter(str.isdigit, cpf))
    if not is_cpf_valid(cpf_formatado):
        return jsonify({'valid': False, 'message': 'CPF com formato inválido.'}), 400
    
    user = User.query.filter_by(cpf=cpf).first()
    if user:
        return jsonify({'valid': False, 'message': 'Este CPF já está registado.'}), 409 # 409 Conflict
        
    return jsonify({'valid': True})

# --- NOVA ROTA PARA A PÁGINA DE SUCESSO ---
@app.route('/registro_sucesso')
def registro_sucesso():
    return render_template('registro_sucesso.html')


# --- Bloco Principal para Executar a Aplicação ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
