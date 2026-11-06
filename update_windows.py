"""Apply an extracted release to an existing local installation, keeping state intact."""
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = {'.env.example','requirements.txt'}
SUFFIXES = {'.py','.cmd','.txt','.md'}


def settings(path):
    result = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1)
            result[key.strip()]=value.strip()
    return result


def release_files(source):
    files=[p for p in source.iterdir() if p.is_file() and (p.name in FILES or (p.suffix in SUFFIXES and not p.name.startswith(('test_','META-'))))]
    for directory in ('public','deploy'):
        files.extend(p for p in (source/directory).rglob('*') if p.is_file())
    for p in files:
        if p.is_symlink() or not p.resolve().is_relative_to(source.resolve()):
            raise ValueError('Pacote contém links inesperados. Não atualizei.')
    return files


def apply_update(source,target,install=True):
    source,target=Path(source).resolve(),Path(target).resolve()
    if source==target:
        raise ValueError('Selecione a pasta antiga do CRM, diferente da pasta extraída da atualização.')
    if not (target/'.env').is_file() or not (target/'INICIAR-NO-WINDOWS.cmd').is_file():
        raise ValueError('Selecione a pasta da instalação existente, onde estão .env e INICIAR-NO-WINDOWS.cmd.')
    for required in ('server.py','launch.py','requirements.txt','public/index.html','public/data/cities.json'):
        if not (source/required).is_file():
            raise ValueError('O pacote está incompleto. Extraia todo o ZIP antes de atualizar.')
    values=settings(target/'.env')
    for address in {'127.0.0.1',values.get('CRM_LISTEN_HOST','127.0.0.1')}:
        with socket.socket() as sock:
            sock.settimeout(.5)
            if sock.connect_ex((address,3000))==0:
                raise ValueError('O CRM ainda está rodando. Pare com Ctrl+C no terminal ou pare a tarefa SaisBlueCRM e tente novamente.')
    database=Path(values.get('CRM_DB') or target/'data'/'crm.sqlite3')
    if not database.is_absolute():database=target/database
    if not database.is_file():
        raise ValueError('Não encontrei o banco configurado. Não atualizei para evitar criar uma instalação vazia.')
    python=target/'.venv'/'Scripts'/'python.exe'
    if install and not python.is_file():
        raise ValueError('Não encontrei o ambiente Python existente. Não atualizei.')
    files=release_files(source)
    stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns()%1000000)
    backup=target/'backups'/('atualizacao-'+stamp)
    backup.mkdir(parents=True)
    with sqlite3.connect(database) as old, sqlite3.connect(backup/'crm.sqlite3') as copy:
        old.backup(copy)
    # Only back up files that will be replaced. Configuration and customer state are never copied over.
    with zipfile.ZipFile(backup/'codigo-anterior.zip','w',zipfile.ZIP_DEFLATED) as previous:
        for p in files:
            relative=p.relative_to(source)
            current=target/relative
            if current.is_file():previous.write(current,str(relative))
    for p in files:
        relative=p.relative_to(source)
        destination=target/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        descriptor,temporary=tempfile.mkstemp(prefix='.crm-update-',dir=destination.parent)
        os.close(descriptor)
        try:
            shutil.copyfile(p,temporary)
            os.replace(temporary,destination)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)
    if install:
        subprocess.run([str(python),'-m','pip','install','-r',str(target/'requirements.txt')],cwd=target,check=True)
    return backup


def main():
    if sys.platform!='win32':raise ValueError('Execute este assistente no servidor Windows.')
    print('SAIS BLUE — atualizar uma instalação existente\n')
    print('Pare o CRM antes. Escolha a pasta ANTIGA, que já contém seus contatos e a configuração.')
    print('O assistente cria backup e preserva .env, .venv e o banco. Não altera firewall, DNS ou WhatsApp.')
    try:
        import tkinter as tk
        from tkinter import filedialog
        window=tk.Tk();window.withdraw()
        chosen=filedialog.askdirectory(title='Selecione a pasta ANTIGA do CRM já instalado')
        window.destroy()
    except ImportError:
        chosen=input('Caminho da pasta antiga: ').strip().strip('"')
    if not chosen:
        print('Nenhuma pasta selecionada. Nada foi alterado.');return
    backup=apply_update(ROOT,Path(chosen))
    print('\nAtualização concluída. Backup salvo em: '+str(backup))
    print('Abra INICIAR-NO-WINDOWS.cmd na pasta ANTIGA para iniciar e atualize a página do navegador.')


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nOperação interrompida. Consulte o backup antes de reiniciar.')
    except Exception as error:
        print('\n'+('A instalação das dependências falhou. Não inicie até resolver com TI; há backup na pasta backups.' if isinstance(error,subprocess.CalledProcessError) else str(error)))
        sys.exit(1)
