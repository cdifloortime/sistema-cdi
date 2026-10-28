import os, sqlite3, secrets, threading, time
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string, abort
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY') or secrets.token_hex(32)
DB=os.environ.get('CDI_DB','cdi.db')
AUTO_DELAY_SECONDS=5

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','recepcao','terapeuta','financeiro')),professional_id INTEGER);
  CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY,name TEXT NOT NULL,active INTEGER DEFAULT 1);
  CREATE TABLE IF NOT EXISTS professionals(id INTEGER PRIMARY KEY,name TEXT NOT NULL,specialty TEXT NOT NULL,payout_cents INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY,patient_id INTEGER NOT NULL REFERENCES patients(id),professional_id INTEGER NOT NULL REFERENCES professionals(id),starts_at TEXT NOT NULL,ends_at TEXT NOT NULL,price_cents INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'agendado' CHECK(status IN ('agendado','realizado','falta','cancelado')),UNIQUE(professional_id,starts_at));
  CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments(id),author_id INTEGER NOT NULL REFERENCES users(id),content TEXT NOT NULL,created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY,appointment_id INTEGER REFERENCES appointments(id),kind TEXT NOT NULL CHECK(kind IN ('receita','despesa','repasse')),description TEXT NOT NULL,amount_cents INTEGER NOT NULL,paid INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,UNIQUE(appointment_id,kind));
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT NOT NULL,entity TEXT NOT NULL,entity_id INTEGER,created_at TEXT NOT NULL);''')
  c.executescript("""CREATE TABLE IF NOT EXISTS session_times(appointment_id INTEGER PRIMARY KEY REFERENCES appointments(id),started_at TEXT,ended_at TEXT,started_by INTEGER,ended_by INTEGER,started_mode TEXT,ended_mode TEXT);
  CREATE TABLE IF NOT EXISTS note_revisions(id INTEGER PRIMARY KEY,note_id INTEGER NOT NULL,old_content TEXT NOT NULL,new_content TEXT NOT NULL,reason TEXT NOT NULL,editor_id INTEGER NOT NULL,changed_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS professional_stamps(professional_id INTEGER PRIMARY KEY REFERENCES professionals(id),stamp_text TEXT NOT NULL);""")
  if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
   username=os.environ.get('CDI_ADMIN_USER','admin'); password=os.environ.get('CDI_ADMIN_PASSWORD')
   if not password: raise RuntimeError('Configure CDI_ADMIN_PASSWORD antes de iniciar pela primeira vez.')
   c.execute('INSERT INTO users(username,password,role) VALUES(?,?,?)',(username,generate_password_hash(password),'admin'))

def reconcile_timers(now=None):
 """Reconcilia horários previstos; não confirma execução clínica."""
 now=now or datetime.now()
 with db() as c:
  cols={r['name'] for r in c.execute('PRAGMA table_info(session_times)')}
  for name in ('started_mode','ended_mode'):
   if name not in cols: c.execute('ALTER TABLE session_times ADD COLUMN '+name+' TEXT')
  rows=c.execute("SELECT a.id,a.starts_at,a.ends_at,a.status,t.started_at,t.ended_at FROM appointments a LEFT JOIN session_times t ON t.appointment_id=a.id WHERE a.status NOT IN ('falta','cancelado') AND a.ends_at>=?",((now-timedelta(days=2)).isoformat(timespec='minutes'),)).fetchall()
  for a in rows:
   start=datetime.fromisoformat(a['starts_at']); end=datetime.fromisoformat(a['ends_at'])
   if not a['started_at'] and now>=start+timedelta(seconds=AUTO_DELAY_SECONDS):
    planned=start+timedelta(seconds=AUTO_DELAY_SECONDS)
    c.execute("INSERT INTO session_times(appointment_id,started_at,started_mode) VALUES(?,?,'automatico') ON CONFLICT(appointment_id) DO UPDATE SET started_at=excluded.started_at,started_mode='automatico' WHERE session_times.started_at IS NULL",(a['id'],planned.isoformat(timespec='seconds')))
   if now>=end:
    c.execute("UPDATE session_times SET ended_at=?,ended_mode='automatico' WHERE appointment_id=? AND started_at IS NOT NULL AND ended_at IS NULL",(end.isoformat(timespec='seconds'),a['id']))

def timer_worker():
 while True:
  try: reconcile_timers()
  except Exception: app.logger.exception('Falha na reconciliação de cronômetros')
  time.sleep(1)

@app.before_request
def sync_timer_on_request():
 if request.endpoint not in ('static',): reconcile_timers()

def audit(c,action,entity,entity_id): c.execute('INSERT INTO audit(user_id,action,entity,entity_id,created_at) VALUES(?,?,?,?,?)',(session.get('uid'),action,entity,entity_id,datetime.now().isoformat(timespec='seconds')))
def money(v): return f'R$ {v/100:,.2f}'.replace(',','X').replace('.',',').replace('X','.')
app.jinja_env.filters['money']=money
BASE='''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CDI Gestão</title><style>body{font-family:system-ui,Arial;background:#f4f7fb;color:#172b42;margin:0}header{background:#153f68;color:white;padding:18px 4%;display:flex;justify-content:space-between;align-items:center}nav{background:white;padding:12px 4%;display:flex;gap:16px;flex-wrap:wrap;border-bottom:1px solid #ddd}nav a{color:#174a78;text-decoration:none;font-weight:600}main{max-width:1150px;margin:25px auto;padding:0 16px}.card{background:white;padding:22px;border-radius:12px;box-shadow:0 1px 7px #dae1ea;margin-bottom:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.stat{font-size:28px;font-weight:750;color:#15678c}input,select,textarea,button{padding:10px;border:1px solid #bccbd9;border-radius:7px;font:inherit;max-width:100%;box-sizing:border-box}label{display:block;margin:12px 0 4px}button{background:#14688d;color:white;border:0;cursor:pointer;margin-top:12px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;border-bottom:1px solid #e2e7ef;text-align:left}th{background:#eef4f9}.scroll{overflow-x:auto}.alert{background:#fff4c9;padding:12px;border-radius:7px;margin-bottom:12px}small{color:#62768b}.inline{display:inline}.inline button{margin:2px}a{color:#14688d}textarea{width:100%;min-height:120px}</style></head><body><header><strong>CDI | Gestão Integrada</strong><span>{{ session.get('username','') }} {% if session.get('uid') %}· <a style="color:white" href="{{url_for('logout')}}">Sair</a>{% endif %}</span></header>{% if session.get('uid') %}<nav><a href="{{url_for('home')}}">Início</a><a href="{{url_for('agenda')}}">{{ 'Meus atendimentos / Evoluções' if session.get('role')=='terapeuta' else 'Agenda e presença' }}</a>{% if session.get('role') in ['admin','recepcao'] %}<a href="{{url_for('patients')}}">Pacientes</a><a href="{{url_for('professionals')}}">Terapeutas</a>{% endif %}{% if session.get('role') in ['admin','financeiro'] %}<a href="{{url_for('finance')}}">Financeiro</a>{% endif %}{% if session.get('role')=='admin' %}<a href="{{url_for('users')}}">Usuários</a>{% endif %}</nav>{% endif %}<main>{% for m in get_flashed_messages() %}<div class="alert">{{m}}</div>{% endfor %}{{body|safe}}</main></body></html>'''
def page(body,**kwargs): return render_template_string(BASE,body=render_template_string(body,**kwargs))
def login_required(f):
 @wraps(f)
 def inner(*a,**kw):
  if not session.get('uid'): return redirect(url_for('login'))
  return f(*a,**kw)
 return inner
def roles(*allowed):
 def deco(f):
  @wraps(f)
  @login_required
  def inner(*a,**kw):
   if session['role'] not in allowed: abort(403)
   return f(*a,**kw)
  return inner
 return deco
def intfield(name): return int(request.form[name])
def cents(name):
 v=request.form[name].strip().replace('.','').replace(',','.')
 from decimal import Decimal
 return int(Decimal(v)*100)
def ownership(a): return session['role']!='terapeuta' or a['professional_id']==session.get('professional_id')

@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with db() as c: u=c.execute('SELECT * FROM users WHERE username=?',(request.form['username'],)).fetchone()
  if u and check_password_hash(u['password'],request.form['password']):
   session.clear();session.update(uid=u['id'],username=u['username'],role=u['role'],professional_id=u['professional_id']);return redirect(url_for('home'))
  flash('Credenciais inválidas')
 return page('''<div class="card" style="max-width:400px;margin:50px auto"><h2>Entrar no CDI</h2><form method="post"><label>Usuário</label><input name="username" required><label>Senha</label><input name="password" type="password" required><button>Entrar</button></form></div>''')
@app.route('/logout')
def logout(): session.clear();return redirect(url_for('login'))
@app.route('/')
@login_required
def home():
 with db() as c:
  today=date.today().isoformat(); w='WHERE substr(starts_at,1,10)=?'; params=[today]
  if session['role']=='terapeuta': w+=' AND professional_id=?';params.append(session.get('professional_id') or -1)
  counts=c.execute('SELECT status,count(*) n FROM appointments '+w+' GROUP BY status',params).fetchall()
  financial=c.execute('SELECT kind,sum(amount_cents) v FROM entries GROUP BY kind').fetchall() if session['role'] in ('admin','financeiro') else []
 return page('''<h1>{{ 'Minhas evoluções' if session.role=='terapeuta' else 'Painel administrativo' }}</h1><div class="grid">{% for r in counts %}<div class="card"><small>Hoje · {{r.status}}</small><div class="stat">{{r.n}}</div></div>{% endfor %}{% for r in financial %}<div class="card"><small>Total lançado · {{r.kind}}</small><div class="stat">{{r.v|money}}</div></div>{% endfor %}</div><div class="card">{{ 'Abra Meus atendimentos / Evoluções para registrar o prontuário diário apenas das sessões atribuídas a você e confirmadas pela recepção.' if session.role=='terapeuta' else 'Use o menu para administrar pacientes, terapeutas e atendimentos. Receitas e repasses são gerados quando a sessão é marcada como realizada.' }}</div>''',counts=counts,financial=financial)
@app.route('/patients',methods=['GET','POST'])
@roles('admin','recepcao')
def patients():
 with db() as c:
  if request.method=='POST':
   name=request.form['name'].strip()
   if not name: abort(400)
   cur=c.execute('INSERT INTO patients(name) VALUES(?)',(name,));audit(c,'criar','patient',cur.lastrowid);return redirect(url_for('patients'))
  rows=c.execute('SELECT * FROM patients ORDER BY name').fetchall()
 return page('''<h2>Pacientes</h2><div class="card"><form method="post"><label>Nome do paciente</label><input name="name" required><button>Cadastrar</button></form></div><div class="card"><div class="scroll"><table><tr><th>ID</th><th>Nome</th></tr>{% for r in rows %}<tr><td>{{r.id}}</td><td>{{r.name}}</td></tr>{% endfor %}</table></div></div>''',rows=rows)
@app.route('/professionals',methods=['GET','POST'])
@roles('admin','recepcao')
def professionals():
 with db() as c:
  if request.method=='POST':
   cur=c.execute('INSERT INTO professionals(name,specialty,payout_cents) VALUES(?,?,?)',(request.form['name'].strip(),request.form['specialty'].strip(),cents('payout')));audit(c,'criar','professional',cur.lastrowid);return redirect(url_for('professionals'))
  rows=c.execute('SELECT * FROM professionals ORDER BY name').fetchall()
 return page('''<h2>Terapeutas</h2><div class="card"><form method="post"><label>Nome</label><input name="name" required><label>Especialidade</label><input name="specialty" required><label>Repasse por sessão (R$)</label><input name="payout" placeholder="80,00" required><button>Cadastrar</button></form></div><div class="card scroll"><table><tr><th>Nome</th><th>Especialidade</th><th>Repasse</th></tr>{% for r in rows %}<tr><td>{{r.name}}</td><td>{{r.specialty}}</td><td>{{r.payout_cents|money}}</td></tr>{% endfor %}</table></div>''',rows=rows)
@app.route('/agenda',methods=['GET','POST'])
@login_required
def agenda():
 with db() as c:
  if request.method=='POST':
   if session['role'] not in ('admin','recepcao'): abort(403)
   pid=intfield('professional_id');start=request.form['starts_at'];end=request.form['ends_at']
   if datetime.fromisoformat(end)<=datetime.fromisoformat(start): flash('Horário final deve ser posterior ao inicial');return redirect(url_for('agenda'))
   overlap=c.execute("SELECT 1 FROM appointments WHERE professional_id=? AND status!='cancelado' AND starts_at<? AND ends_at>?",(pid,end,start)).fetchone()
   if overlap: flash('Conflito na agenda do terapeuta');return redirect(url_for('agenda'))
   cur=c.execute('INSERT INTO appointments(patient_id,professional_id,starts_at,ends_at,price_cents) VALUES(?,?,?,?,?)',(intfield('patient_id'),pid,start,end,cents('price')));audit(c,'agendar','appointment',cur.lastrowid);return redirect(url_for('agenda'))
  patients=c.execute('SELECT * FROM patients WHERE active=1 ORDER BY name').fetchall();pros=c.execute('SELECT * FROM professionals ORDER BY name').fetchall()
  d=request.args.get('date',date.today().isoformat());sql='''SELECT a.*,p.name patient,t.name professional,t.specialty FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN professionals t ON t.id=a.professional_id WHERE substr(a.starts_at,1,10)=?''';params=[d]
  if session['role']=='terapeuta': sql+=' AND a.professional_id=?';params.append(session.get('professional_id') or -1)
  rows=c.execute(sql+' ORDER BY a.starts_at',params).fetchall()
 return page('''<h2>{{ 'Meus atendimentos / Evoluções' if session.role=='terapeuta' else 'Agenda e lista de presença' }}</h2>{% if session.role in ['admin','recepcao'] %}<div class="card"><h3>Novo atendimento</h3><form method="post"><div class="grid"><div><label>Paciente</label><select name="patient_id" required>{% for p in patients %}<option value="{{p.id}}">{{p.name}}</option>{% endfor %}</select></div><div><label>Terapeuta</label><select name="professional_id" required>{% for p in pros %}<option value="{{p.id}}">{{p.name}} · {{p.specialty}}</option>{% endfor %}</select></div><div><label>Início</label><input type="datetime-local" name="starts_at" required></div><div><label>Fim</label><input type="datetime-local" name="ends_at" required></div><div><label>Valor da sessão (R$)</label><input name="price" placeholder="150,00" required></div></div><button>Agendar</button></form></div>{% endif %}<div class="card"><form method="get"><label>Data</label><input type="date" name="date" value="{{d}}"><button>Consultar</button></form></div><div class="card scroll"><table><tr><th>Horário</th><th>Paciente</th><th>Terapeuta</th><th>Status</th><th>Ações</th></tr>{% for r in rows %}<tr><td>{{r.starts_at[11:16]}}–{{r.ends_at[11:16]}}</td><td>{{r.patient}}</td><td>{{r.professional}}<br><small>{{r.specialty}}</small></td><td>{{r.status}}</td><td><a href="{{url_for('appointment',id=r.id)}}">Abrir atendimento</a></td></tr>{% endfor %}</table></div></div>''',patients=patients,pros=pros,rows=rows,d=d)
@app.route('/appointment/<int:id>',methods=['GET','POST'])
@login_required
def appointment(id):
 with db() as c:
  a=c.execute('''SELECT a.*,p.name patient,t.name professional,t.specialty,t.payout_cents FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN professionals t ON t.id=a.professional_id WHERE a.id=?''',(id,)).fetchone()
  if not a: abort(404)
  if not ownership(a): abort(403)
  if request.method=='POST':
   action=request.form.get('action')
   if action=='status':
    if session['role'] not in ('admin','recepcao'): abort(403)
    status=request.form['status']
    if status not in ('agendado','realizado','falta','cancelado'): abort(400)
    c.execute('UPDATE appointments SET status=? WHERE id=?',(status,id))
    if status=='realizado':
     for kind,amount,desc in [('receita',a['price_cents'],'Sessão: '+a['patient']),('repasse',a['payout_cents'],'Repasse: '+a['professional'])]:
      c.execute('INSERT OR IGNORE INTO entries(appointment_id,kind,description,amount_cents,created_at) VALUES(?,?,?,?,?)',(id,kind,desc,amount,datetime.now().isoformat(timespec='seconds')))
    else:
     c.execute('DELETE FROM entries WHERE appointment_id=? AND paid=0',(id,))
     if c.execute('SELECT 1 FROM entries WHERE appointment_id=? AND paid=1',(id,)).fetchone(): flash('Há lançamentos pagos: ajuste manual obrigatório antes de encerrar.')
    audit(c,'status:'+status,'appointment',id)
   elif action in ('start_timer','end_timer'):
    if session['role']!='terapeuta': abort(403)
    now=datetime.now().astimezone().isoformat(timespec='seconds')
    t=c.execute('SELECT * FROM session_times WHERE appointment_id=?',(id,)).fetchone()
    if action=='start_timer':
     if t and t['started_at']: abort(409)
     if datetime.now() < datetime.fromisoformat(a['starts_at']): abort(409)
     c.execute("INSERT INTO session_times(appointment_id,started_at,started_by,started_mode) VALUES(?,?,?,'manual') ON CONFLICT(appointment_id) DO UPDATE SET started_at=excluded.started_at,started_by=excluded.started_by,started_mode='manual' WHERE session_times.started_at IS NULL",(id,now,session['uid']))
    else:
     if not t or t['ended_at']: abort(409)
     c.execute("UPDATE session_times SET ended_at=?,ended_by=?,ended_mode='manual' WHERE appointment_id=?",(now,session['uid'],id))
    audit(c,action,'appointment',id)
   elif action=='stamp':
    if session['role']!='terapeuta': abort(403)
    stamp=request.form.get('stamp','').strip()
    if not stamp or len(stamp)>500: abort(400)
    c.execute('INSERT INTO professional_stamps(professional_id,stamp_text) VALUES(?,?) ON CONFLICT(professional_id) DO UPDATE SET stamp_text=excluded.stamp_text',(a['professional_id'],stamp))
    audit(c,'atualizar_carimbo','professional',a['professional_id'])
   elif action=='note':
    if session['role'] not in ('admin','terapeuta'): abort(403)
    if a['status']!='realizado': flash('Confirme o atendimento realizado antes da evolução');return redirect(url_for('appointment',id=id))
    content=request.form['content'].strip()
    if not content: abort(400)
    existing=c.execute('SELECT * FROM notes WHERE appointment_id=?',(id,)).fetchone()
    if existing:
     if existing['author_id']!=session['uid']: abort(403)
     reason=request.form.get('reason','').strip()
     if not reason or len(reason)>500: abort(400)
     if existing['content']!=content:
      c.execute('INSERT INTO note_revisions(note_id,old_content,new_content,reason,editor_id,changed_at) VALUES(?,?,?,?,?,?)',(existing['id'],existing['content'],content,reason,session['uid'],datetime.now().astimezone().isoformat(timespec='seconds')))
      c.execute('UPDATE notes SET content=? WHERE id=?',(content,existing['id']))
      audit(c,'retificar','note',existing['id'])
    else:
     t=c.execute('SELECT * FROM session_times WHERE appointment_id=?',(id,)).fetchone()
     if not t or not t['ended_at']: flash('Finalize o cronômetro antes de salvar.');return redirect(url_for('appointment',id=id))
     cur=c.execute('INSERT INTO notes(appointment_id,author_id,content,created_at) VALUES(?,?,?,?)',(id,session['uid'],content,datetime.now().astimezone().isoformat(timespec='seconds')));audit(c,'registrar','note',cur.lastrowid)
   else: abort(400)
   return redirect(url_for('appointment',id=id))
  note=c.execute('SELECT n.*,u.username author FROM notes n JOIN users u ON u.id=n.author_id WHERE appointment_id=?',(id,)).fetchone()
  timer=c.execute('SELECT * FROM session_times WHERE appointment_id=?',(id,)).fetchone()
  stamp=c.execute('SELECT stamp_text FROM professional_stamps WHERE professional_id=?',(a['professional_id'],)).fetchone()
  revisions=c.execute('SELECT r.*,u.username editor FROM note_revisions r JOIN users u ON u.id=r.editor_id WHERE note_id=? ORDER BY r.id DESC',(note['id'],)).fetchall() if note else []
 return page('''<h2>Atendimento #{{a.id}}</h2><div class="card"><p><b>Paciente:</b> {{a.patient}} | <b>Terapeuta:</b> {{a.professional}} ({{a.specialty}})</p><p><b>Agendado:</b> {{a.starts_at}} até {{a.ends_at}} | <b>Status:</b> {{a.status}}</p>{% if session.role in ['admin','recepcao'] %}<form method="post"><input type="hidden" name="action" value="status"><label>Presença / situação</label><select name="status">{% for s in ['agendado','realizado','falta','cancelado'] %}<option value="{{s}}" {% if a.status==s %}selected{% endif %}>{{s}}</option>{% endfor %}</select><button>Atualizar situação</button></form>{% endif %}</div><div class="card"><h3>Controle de horários (não comprova presença)</h3><p>Início registrado: {{timer.started_at if timer and timer.started_at else 'Aguardando'}} ({{timer.started_mode if timer and timer.started_mode else '—'}})<br>Fim registrado: {{timer.ended_at if timer and timer.ended_at else 'Aguardando'}} ({{timer.ended_mode if timer and timer.ended_mode else '—'}})</p><small>Início automático 5 segundos após o horário agendado; encerramento automático no horário final. A recepção confirma a realização.</small>{% if session.role=='terapeuta' %}{% if not timer %}<form method="post"><input type="hidden" name="action" value="start_timer"><button>▶ Iniciar terapia</button></form>{% elif not timer.ended_at %}<form method="post"><input type="hidden" name="action" value="end_timer"><button>■ Finalizar terapia</button></form>{% endif %}{% endif %}</div><div class="card"><h3>Carimbo profissional</h3><p style="white-space:pre-wrap">{{stamp.stamp_text if stamp else 'Não cadastrado'}}</p>{% if session.role=='terapeuta' %}<form method="post"><input type="hidden" name="action" value="stamp"><label>Nome, especialidade e registro do conselho (quando aplicável)</label><textarea name="stamp" maxlength="500" required>{{stamp.stamp_text if stamp else ''}}</textarea><button>Salvar carimbo</button></form>{% endif %}</div><div class="card"><h3>Prontuário diário</h3>{% if note %}<p><small>Registrado por {{note.author}} em {{note.created_at}}</small></p>{% endif %}{% if session.role=='terapeuta' and a.status=='realizado' and (not note or note.author_id==session.uid) %}<form method="post"><input type="hidden" name="action" value="note"><label>Evolução clínica</label><textarea name="content" required>{{note.content if note else ''}}</textarea>{% if note %}<label>Motivo da correção (obrigatório)</label><input name="reason" maxlength="500" required>{% endif %}<button>{{'Salvar correção com histórico' if note else 'Salvar prontuário'}}</button></form>{% elif note %}<p style="white-space:pre-wrap">{{note.content}}</p>{% else %}<p>Aguardando confirmação da recepção e registro pelo terapeuta.</p>{% endif %}{% if revisions %}<h4>Histórico de retificações</h4>{% for r in revisions %}<details><summary>{{r.changed_at}} — {{r.editor}} — {{r.reason}}</summary><p><b>Versão anterior:</b></p><p style="white-space:pre-wrap">{{r.old_content}}</p></details>{% endfor %}{% endif %}</div>''',a=a,note=note,timer=timer,stamp=stamp,revisions=revisions)
@app.route('/finance',methods=['GET','POST'])
@roles('admin','financeiro')
def finance():
 with db() as c:
  if request.method=='POST':
   if request.form['action']=='add':
    kind=request.form['kind']
    if kind not in ('receita','despesa'): abort(400)
    cur=c.execute('INSERT INTO entries(kind,description,amount_cents,created_at) VALUES(?,?,?,?)',(kind,request.form['description'].strip(),cents('amount'),datetime.now().isoformat(timespec='seconds')));audit(c,'criar','entry',cur.lastrowid)
   elif request.form['action']=='paid':
    eid=intfield('id');c.execute('UPDATE entries SET paid=1 WHERE id=?',(eid,));audit(c,'quitar','entry',eid)
   else: abort(400)
   return redirect(url_for('finance'))
  rows=c.execute('SELECT * FROM entries ORDER BY id DESC LIMIT 200').fetchall()
  sums=c.execute('SELECT kind,paid,sum(amount_cents) total FROM entries GROUP BY kind,paid').fetchall()
 return page('''<h2>Financeiro e repasses</h2><div class="grid">{% for s in sums %}<div class="card"><small>{{s.kind}} · {{'pago/recebido' if s.paid else 'pendente'}}</small><div class="stat">{{s.total|money}}</div></div>{% endfor %}</div><div class="card"><h3>Lançamento manual</h3><form method="post"><input type="hidden" name="action" value="add"><label>Tipo</label><select name="kind"><option value="receita">Receita</option><option value="despesa">Despesa</option></select><label>Descrição</label><input name="description" required><label>Valor (R$)</label><input name="amount" required placeholder="100,00"><button>Lançar</button></form></div><div class="card scroll"><table><tr><th>Tipo</th><th>Descrição</th><th>Valor</th><th>Situação</th><th>Ação</th></tr>{% for r in rows %}<tr><td>{{r.kind}}</td><td>{{r.description}}</td><td>{{r.amount_cents|money}}</td><td>{{'Quitado' if r.paid else 'Pendente'}}</td><td>{% if not r.paid %}<form method="post" class="inline"><input type="hidden" name="action" value="paid"><input type="hidden" name="id" value="{{r.id}}"><button>Marcar quitado</button></form>{% endif %}</td></tr>{% endfor %}</table></div>''',rows=rows,sums=sums)
@app.route('/users',methods=['GET','POST'])
@roles('admin')
def users():
 with db() as c:
  if request.method=='POST':
   role=request.form['role'];pid=request.form.get('professional_id') or None
   if role not in ('admin','recepcao','terapeuta','financeiro') or (role=='terapeuta' and not pid): abort(400)
   cur=c.execute('INSERT INTO users(username,password,role,professional_id) VALUES(?,?,?,?)',(request.form['username'].strip(),generate_password_hash(request.form['password']),role,pid if role=='terapeuta' else None));audit(c,'criar','user',cur.lastrowid);return redirect(url_for('users'))
  pros=c.execute('SELECT * FROM professionals').fetchall();rows=c.execute('SELECT username,role FROM users').fetchall()
 return page('''<h2>Usuários e permissões</h2><div class="card"><form method="post"><label>Usuário</label><input name="username" required><label>Senha</label><input name="password" type="password" minlength="12" required><label>Perfil</label><select name="role"><option value="recepcao">Recepção</option><option value="terapeuta">Terapeuta</option><option value="financeiro">Financeiro</option><option value="admin">Administrador</option></select><label>Profissional vinculado (obrigatório para terapeuta)</label><select name="professional_id"><option value="">Nenhum</option>{% for p in pros %}<option value="{{p.id}}">{{p.name}}</option>{% endfor %}</select><button>Criar usuário</button></form></div><div class="card"><table><tr><th>Usuário</th><th>Perfil</th></tr>{% for r in rows %}<tr><td>{{r.username}}</td><td>{{r.role}}</td></tr>{% endfor %}</table></div>''',pros=pros,rows=rows)

if __name__=='__main__':
 init();threading.Thread(target=timer_worker,daemon=True).start();app.run(host='127.0.0.1',port=int(os.environ.get('PORT',5000)),debug=False)
