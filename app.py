import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, make_response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from PIL import Image

template_dir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, template_folder=os.path.join(template_dir, 'templates'), static_folder=os.path.join(template_dir, 'static'))
app.secret_key = 'chave_secreta_super_segura'

UPLOAD_FOLDER = os.path.join(template_dir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(template_dir, 'imoveis.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024
db = SQLAlchemy(app)

class Imovel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    negocio = db.Column(db.String(10), nullable=False, default='venda')
    preco_num = db.Column(db.Float, nullable=False)
    preco = db.Column(db.String(50), nullable=False)
    localizacao = db.Column(db.String(100), nullable=False)
    imagem = db.Column(db.String(250), nullable=False)
    link = db.Column(db.String(250), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    fotos = db.relationship('FotoImovel', backref='imovel', cascade="all, delete-orphan", lazy=True)

class FotoImovel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    imovel_id = db.Column(db.Integer, db.ForeignKey('imovel.id'), nullable=False)
    caminho = db.Column(db.String(250), nullable=False)

with app.app_context():
    db.create_all()

def salvar_arquivo(file):
    if file:
        # Se o filename estiver vazio (comum em Blobs do CropperJS), geramos um nome padrão
        filename_original = file.filename if file.filename else "capa_cortada.jpg"
        ext = filename_original.rsplit('.', 1)[1].lower() if '.' in filename_original else 'jpg'
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            imagem = Image.open(file)
            
            if imagem.mode in ('RGBA', 'LA'):
                fundo = Image.new('RGB', imagem.size, (255, 255, 255))
                fundo.paste(imagem, mask=imagem.split()[3])
                imagem = fundo
            elif imagem.mode != 'RGB':
                imagem = imagem.convert('RGB')
            
            max_largura = 1920
            if imagem.width > max_largura:
                nova_altura = int((max_largura / imagem.width) * imagem.height)
                imagem = imagem.resize((max_largura, nova_altura), Image.Resampling.LANCZOS)
            
            imagem.save(filepath, 'JPEG', quality=82, optimize=True)
            return f"uploads/{filename}"
        except Exception as e:
            print(f"Erro ao processar imagem com Pillow: {e}")
            return None
            
    return None

PERFIL = {
    "nome": "Rose Carvalho",
    "cargo": "Corretora de imóveis",
    "corretora": "RE/MAX",
    "foto": "corretora.png",
    "logo": "logobranca.png",
    "whatsapp": "559884633229",
    "instagram": "https://www.instagram.com/rosecorretoraslz/",
    "website": "https://www.remax.com.br/pt-br/corretores/maranhao/sao-luis-sao-francisco/rouselyn-arocha-de-carvalho/720941048"
}

@app.context_processor
def inject_globals():
    return dict(perfil=PERFIL)

@app.route("/")
def index():
    tem_venda = db.session.query(Imovel).filter_by(negocio='venda').count() > 0
    tem_aluguel = db.session.query(Imovel).filter_by(negocio='aluguel').count() > 0

    imoveis_venda = Imovel.query.filter_by(negocio='venda').order_by(Imovel.preco_num.desc()).all()
    imoveis_aluguel = Imovel.query.filter_by(negocio='aluguel').order_by(Imovel.preco_num.desc()).all()

    aba_param = request.args.get('negocio')
    
    if aba_param == 'aluguel' and not tem_aluguel:
        aba_ativa = 'venda'
    elif aba_param in ['venda', 'aluguel']:
        aba_ativa = aba_param
    else:
        if tem_venda:
            aba_ativa = 'venda'
        elif tem_aluguel:
            aba_ativa = 'aluguel'
        else:
            aba_ativa = 'venda'
    
    imoveis = imoveis_aluguel if aba_ativa == 'aluguel' else imoveis_venda

    return render_template(
        "index.html", 
        imoveis=imoveis,
        imoveis_venda=imoveis_venda, 
        imoveis_aluguel=imoveis_aluguel, 
        tem_venda=tem_venda, 
        tem_aluguel=tem_aluguel, 
        aba_ativa=aba_ativa
    )

@app.route("/imovel/<int:id>")
def detalhe_imovel(id):
    imovel = Imovel.query.get_or_404(id)
    return render_template("detalhes.html", imovel=imovel)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    erro = None
    if request.method == "POST":
        senha = request.form.get("senha")
        if senha == "Afonso07":
            session['admin_logado'] = True
            return redirect(url_for("admin_painel"))
        else:
            erro = "Senha incorreta!"
    return render_template("login.html", erro=erro)

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logado', None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
def admin_painel():
    if not session.get('admin_logado'):
        return redirect(url_for("admin_login"))
    
    imoveis = Imovel.query.order_by(Imovel.id.desc()).all()
    response = make_response(render_template("admin.html", imoveis=imoveis))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/admin/adicionar", methods=["GET", "POST"])
def adicionar_imovel():
    if not session.get('admin_logado'): return redirect(url_for("admin_login"))
    
    if request.method == "POST":
        tipo_cadastro = request.form.get("tipo_cadastro", "completo")
        negocio = request.form.get("negocio", "venda")
        titulo = request.form.get("titulo")
        preco_limpo = request.form.get("preco_num", "").replace(".", "").replace(",", "")
        preco_num = float(preco_limpo) if preco_limpo else 0.0
        preco_formatado = f"R$ {int(preco_num):,}".replace(",", ".")
        localizacao = request.form.get("localizacao")

        capa_file = request.files.get('imagem_arquivo')
        imagem_capa = salvar_arquivo(capa_file)

        if not imagem_capa:
            return "Erro ao processar a foto de capa. Tente outra imagem.", 400

        if tipo_cadastro == "link":
            link = request.form.get("link")
            descricao = None
        else:
            link = None
            descricao = request.form.get("descricao")

        novo = Imovel(
            titulo=titulo, 
            negocio=negocio,
            preco_num=preco_num, 
            preco=preco_formatado, 
            localizacao=localizacao, 
            imagem=imagem_capa, 
            link=link, 
            descricao=descricao
        )
        db.session.add(novo)
        db.session.commit()

        if tipo_cadastro == "completo":
            galeria_files = request.files.getlist('fotos_galeria')
            galeria_files = [f for f in galeria_files if f and f.filename != '']
            
            if len(galeria_files) > 20:
                galeria_files = galeria_files[:20]

            for f in galeria_files:
                caminho_foto = salvar_arquivo(f)
                if caminho_foto:
                    nova_foto = FotoImovel(imovel_id=novo.id, caminho=caminho_foto)
                    db.session.add(nova_foto)
            db.session.commit()

        return redirect(url_for("admin_painel"))

    return render_template("adicionar.html")

@app.route("/admin/editar/<int:id>", methods=["GET", "POST"])
def editar_imovel(id):
    if not session.get('admin_logado'): return redirect(url_for("admin_login"))
    imovel = Imovel.query.get_or_404(id)

    if request.method == "POST":
        imovel.titulo = request.form.get("titulo")
        imovel.negocio = request.form.get("negocio", "venda")
        preco_limpo = request.form.get("preco_num", "").replace(".", "").replace(",", "")
        imovel.preco_num = float(preco_limpo) if preco_limpo else 0.0
        imovel.preco = f"R$ {int(imovel.preco_num):,}".replace(",", ".")
        imovel.localizacao = request.form.get("localizacao")

        capa_file = request.files.get('imagem_arquivo')
        if capa_file and capa_file.filename != '':
            nova_capa = salvar_arquivo(capa_file)
            if nova_capa:
                imovel.imagem = nova_capa

        # Verifica se o imóvel é do tipo link ou completo
        if imovel.link is not None and imovel.link != '':
            imovel.link = request.form.get("link")
        else:
            imovel.descricao = request.form.get("descricao")
            
            # Pega e limpa a lista de arquivos para garantir que só contêm arquivos válidos
            galeria_files = request.files.getlist('fotos_galeria')
            galeria_files = [f for f in galeria_files if f and f.filename != '']
            
            fotos_atuais_count = len(imovel.fotos)
            vagas_restantes = 20 - fotos_atuais_count

            if vagas_restantes <= 0:
                galeria_files = []
            elif len(galeria_files) > vagas_restantes:
                galeria_files = galeria_files[:vagas_restantes]

            for f in galeria_files:
                caminho_foto = salvar_arquivo(f)
                if caminho_foto:
                    nova_foto = FotoImovel(imovel_id=imovel.id, caminho=caminho_foto)
                    db.session.add(nova_foto)

        db.session.commit()
        return redirect(url_for("admin_painel"))

    return render_template("editar.html", imovel=imovel)

@app.route("/admin/excluir_foto/<int:foto_id>")
def excluir_foto(foto_id):
    if not session.get('admin_logado'): return redirect(url_for("admin_login"))
    foto = FotoImovel.query.get_or_404(foto_id)
    imovel_id = foto.imovel_id
    
    path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(foto.caminho))
    if os.path.exists(path): os.remove(path)
    
    db.session.delete(foto)
    db.session.commit()
    return redirect(url_for("editar_imovel", id=imovel_id))

@app.route("/admin/excluir/<int:id>")
def excluir_imovel(id):
    if not session.get('admin_logado'): return redirect(url_for("admin_login"))
    imovel = Imovel.query.get_or_404(id)
    
    if imovel.imagem and imovel.imagem.startswith('uploads/'):
        path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(imovel.imagem))
        if os.path.exists(path): os.remove(path)
        
    for foto in imovel.fotos:
        path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(foto.caminho))
        if os.path.exists(path): os.remove(path)

    db.session.delete(imovel)
    db.session.commit()
    return redirect(url_for("admin_painel"))

@app.route('/manifest.json')
def manifest():
    return send_from_directory(app.static_folder, 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    response = make_response(send_from_directory(app.static_folder, 'sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)