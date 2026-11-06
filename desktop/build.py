"""Build a small Windows .NET Framework GUI with the official Roslyn compiler."""
import argparse
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--dotnet',required=True,help='dotnet executable from the SDK')
parser.add_argument('--compiler',required=True,help='SDK Roslyn/bincore/csc.dll')
parser.add_argument('--refs',required=True,help='Official .NET Framework v4.8 reference assemblies')
args=parser.parse_args()
names=('mscorlib','System','System.Core','System.Drawing','System.Windows.Forms','System.Management',
       'System.IO.Compression','System.Web.Extensions','System.Web','System.Configuration','System.Xml')
references=[Path(args.refs)/(name+'.dll') for name in names]
if any(not p.is_file() for p in references):raise SystemExit('Reference assemblies missing')
subprocess.run([args.dotnet,args.compiler,'/nologo','/target:winexe','/platform:anycpu','/optimize+',
                '/deterministic+','/nostdlib+','/win32manifest:'+str(ROOT/'app.manifest'),
                '/out:'+str(ROOT/'SaisBlue-Atualizador.exe'),
                *['/reference:'+str(p) for p in references],str(ROOT/'Updater.cs')],check=True)
