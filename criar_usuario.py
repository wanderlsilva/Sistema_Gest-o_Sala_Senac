from werkzeug.security import generate_password_hash

from getpass import getpass

senha = getpass("Digite a senha do usuario: ")
senha_protegida = generate_password_hash(senha)

print("\n Senha protegida: ")
print(senha_protegida)