# create_admin.py
from app import app, db
from models import User

def criar_ou_atualizar_admin():
    """
    Esta função cria o utilizador administrador se ele não existir
    ou atualiza a sua palavra-passe se ele já existir.
    """
    with app.app_context():
        # Garante que todas as tabelas da base de dados estão criadas
        db.create_all()

        admin_cpf = '000.000.000-00'
        admin_pass = 'Messi@3012'

        # Procura o utilizador admin
        admin_user = User.query.filter_by(cpf=admin_cpf).first()

        if admin_user:
            print(f"Utilizador admin com CPF {admin_cpf} já existe. A atualizar a palavra-passe...")
            admin_user.set_password(admin_pass)
        else:
            print(f"A criar um novo utilizador admin com CPF {admin_cpf}...")
            admin_user = User(
                full_name='Administrador do Sistema',
                cpf=admin_cpf,
                birth_date='01/01/2000',
                condominio_name='N/A',
                apartment_address='N/A',
                is_admin=True
            )
            admin_user.set_password(admin_pass)
            db.session.add(admin_user)
        
        # Guarda as alterações
        db.session.commit()
        print("\n>>> Operação concluída com sucesso! <<<")
        print(f"CPF: {admin_cpf}")
        print(f"Palavra-passe: {admin_pass}")

# Executa a função quando o script é chamado diretamente
if __name__ == '__main__':
    criar_ou_atualizar_admin()