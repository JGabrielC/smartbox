import os
import datetime
import requests
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from models import db, User, Condominio, Product, Inventory, Sale
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from PIL import Image
import secrets
from datetime import timedelta

# --- Configuração da Aplicação ---
app = Flask(__name__)
# ... (o resto da sua configuração, sem alterações) ...

db.init_app(app)
# ... (o resto da sua configuração do LoginManager) ...

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTA DE PAGAMENTO (LÓGICA DO QR CODE CORRIGIDA) ---
@app.route('/finalizar_compra_pix', methods=['GET', 'POST'])
@login_required
def finalizar_compra_pix():
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('user_dashboard'))

    # ... (cálculo do total e criação do pedido no Mercado Pago) ...
    
    # Após a criação do pedido, o Mercado Pago devolve um 'id' de pagamento
    payment_id = response.json().get('id')
    
    # Atualiza todas as vendas no banco de dados com este ID de pagamento
    for sale in sales_group:
        sale.payment_id = str(payment_id)
        sale.status = 'pending' # Garante que o status inicial é pendente
    db.session.commit()

    # O QR Code que o cliente vai usar para abrir a porta é o ID do pagamento
    qr_code_de_acesso = str(payment_id)

    # ... (lógica para mostrar a página de sucesso com os dois QR Codes) ...
    return render_template('pagamento_sucesso.html', qr_code_pix=pix_qr_code, qr_code_acesso=qr_code_de_acesso)


# --- API DE VERIFICAÇÃO (LÓGICA CORRIGIDA E MAIS SEGURA) ---
@app.route('/api/liberar_geladeira/<string:payment_id>', methods=['GET'])
def api_liberar_geladeira(payment_id):
    # Procura por QUALQUER venda que tenha este payment_id
    # Usamos 'first()' porque todas as vendas daquela compra terão o mesmo ID
    sale = Sale.query.filter_by(payment_id=payment_id).first()

    # Se não encontrar nenhuma venda com este ID, recusa.
    if not sale:
        return jsonify({'status': 'error', 'message': 'Compra não encontrada'}), 404

    # Busca o status atual do pagamento no Mercado Pago para ter 100% de certeza
    headers = {'Authorization': f'Bearer {MERCADO_PAGO_ACCESS_TOKEN}'}
    mp_response = requests.get(f'https://api.mercadopago.com/v1/payments/{payment_id}', headers=headers)
    
    if mp_response.status_code != 200:
        return jsonify({'status': 'error', 'message': 'Erro ao verificar o pagamento'}), 500

    payment_status = mp_response.json().get('status')

    # A ÚNICA condição para abrir a porta é o pagamento estar 'approved'
    # E o nosso registo interno ainda não ter sido usado ('completed')
    if payment_status == 'approved' and sale.status != 'completed':
        # MUITO IMPORTANTE: Marca todas as vendas desta compra como completas
        # para que o QR Code não possa ser usado novamente.
        Sale.query.filter_by(payment_id=payment_id).update({'status': 'completed'})
        db.session.commit()
        
        return jsonify({'status': 'ok', 'message': 'Acesso liberado'})
    
    elif sale.status == 'completed':
        return jsonify({'status': 'error', 'message': 'Este QR Code já foi utilizado.'}), 403 # Forbidden
    else:
        return jsonify({'status': 'error', 'message': 'Pagamento não aprovado ou pendente.'}), 402 # Payment Required


# (O resto do seu app.py, com todas as outras rotas, continua aqui inalterado)

