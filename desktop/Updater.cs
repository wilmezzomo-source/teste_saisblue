using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Management;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyTitle("Sais Blue CRM — Atualizador")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyInformationalVersion("2026.11.13.1")]

internal sealed class UserError : Exception { public UserError(string message) : base(message) {} }

internal static class Program {
    internal const string Channel = "https://raw.githubusercontent.com/wilmezzomo-source/teste_saisblue/crm-windows/windows-release.json";
    internal static readonly string Home = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SaisBlueCRM");
    internal static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    internal static void Diagnostic(Exception error) {
        try { Directory.CreateDirectory(Home); File.AppendAllText(Path.Combine(Home, "updater-ui.log"), error.GetType().FullName + ": " + error.Message + Environment.NewLine + error.StackTrace + Environment.NewLine); } catch {}
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetLongPathName(string shortPath, StringBuilder longPath, uint capacity);
    internal static string Canonical(string path) {
        var buffer = new StringBuilder(32768);
        if (GetLongPathName(path, buffer, (uint)buffer.Capacity) > 0) path = buffer.ToString();
        return Path.GetFullPath(path);
    }

    internal static string Quote(string value) {
        int trailing = value.Length - value.TrimEnd('\\').Length;
        return "\"" + value.Replace("\"", "\\\"") + new string('\\', trailing) + "\"";
    }
    [STAThread]
    public static void Main(string[] args) {
        if (Environment.OSVersion.Platform != PlatformID.Win32NT) return;
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try {
            Directory.CreateDirectory(Home);
            string original = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string automatic = null;
            int actionIndex = Array.IndexOf(args, "--action");
            if (actionIndex >= 0 && actionIndex + 1 < args.Length && new[] { "start", "stop", "update" }.Contains(args[actionIndex + 1])) automatic = args[actionIndex + 1];
            if (!args.Contains("--staged")) {
                string folder = Path.Combine(Home, "cache", Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(folder);
                string staged = Path.Combine(folder, "SaisBlue-Atualizador.exe");
                File.Copy(Assembly.GetExecutingAssembly().Location, staged);
                Process.Start(new ProcessStartInfo(staged, "--staged --hint " + Quote(original) + (automatic == null ? "" : " --action " + automatic)) { UseShellExecute = false });
                return;
            }
            string hint = null;
            int idx = Array.IndexOf(args, "--hint");
            if (idx >= 0 && idx + 1 < args.Length) hint = args[idx + 1];
            Application.Run(new UpdaterForm(hint, automatic));
        } catch (Exception error) {
            Diagnostic(error);
            MessageBox.Show("Não consegui abrir o atualizador. Execute no servidor Windows e confira a permissão da sua conta para gravar arquivos.", "Sais Blue CRM");
        }
    }
    internal static bool IsInstallation(string folder) {
        try {
            return !folder.StartsWith("\\\\") && File.Exists(Path.Combine(folder, ".env")) &&
                File.Exists(Path.Combine(folder, "server.py")) && File.Exists(Path.Combine(folder, "launch.py")) &&
                File.Exists(Path.Combine(folder, ".venv", "Scripts", "python.exe"));
        } catch { return false; }
    }
    internal static string Discover(string hint) {
        var candidates = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        try {
            using (var search = new ManagementObjectSearcher("SELECT ExecutablePath,CommandLine FROM Win32_Process WHERE Name='python.exe' OR Name='pythonw.exe'")) {
                foreach (ManagementObject p in search.Get()) {
                    string exe = p["ExecutablePath"] as string;
                    string command = p["CommandLine"] as string ?? "";
                    if (exe != null && exe.EndsWith("\\.venv\\Scripts\\python.exe", StringComparison.OrdinalIgnoreCase)) {
                        string folder = Canonical(exe.Substring(0, exe.Length - "\\.venv\\Scripts\\python.exe".Length));
                        if (IsInstallation(folder) && (command.Contains("launch.py") || command.Contains("setup_windows.py") || command.Contains("iniciar_https.py"))) candidates.Add(folder);
                    }
                    foreach (Match m in Regex.Matches(command, "(?:\"(?<path>[^\"]+\\\\(?:launch|setup_windows|iniciar_https|server)\\.py)\"|(?<path>[A-Za-z]:\\\\[^\\s\"]+\\\\(?:launch|setup_windows|iniciar_https|server)\\.py))", RegexOptions.IgnoreCase)) {
                        string folder = Canonical(Path.GetDirectoryName(m.Groups["path"].Value));
                        if (IsInstallation(folder)) candidates.Add(folder);
                    }
                }
            }
        } catch (Exception error) { Diagnostic(error); }
        if (candidates.Count == 1) return candidates.First();
        string saved = Path.Combine(Home, "installation.txt");
        if (File.Exists(saved)) { string folder = File.ReadAllText(saved).Trim(); if (IsInstallation(folder)) return folder; }
        if (!String.IsNullOrWhiteSpace(hint) && IsInstallation(hint)) return hint;
        if (IsInstallation(@"C:\SaisBlueCRM")) return @"C:\SaisBlueCRM";
        return "";
    }
    internal static string DownloadPackage(Action<string, int> report) {
        report("Conferindo a atualização disponível…", 5);
        string folder = Path.Combine(Home, "packages", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        string manifestPath = Path.Combine(folder, "release.json");
        Download(Channel + "?check=" + Guid.NewGuid().ToString("N"), manifestPath, 16384);
        var manifest = Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(manifestPath));
        if (!manifest.ContainsKey("schema") || Convert.ToInt32(manifest["schema"]) != 1) throw new UserError("O pacote de atualização não foi reconhecido. O CRM continua como estava.");
        string commit = Convert.ToString(manifest["commit"]), hash = Convert.ToString(manifest["sha256"]);
        if (!Regex.IsMatch(commit, "\\A[a-f0-9]{40}\\z") || !Regex.IsMatch(hash, "\\A[a-f0-9]{64}\\z")) throw new UserError("Não consegui conferir a integridade do pacote. O CRM continua como estava.");
        report("Baixando a versão " + Convert.ToString(manifest["version"]) + "…", 15);
        string zipPath = Path.Combine(folder, "release.zip");
        Download("https://codeload.github.com/wilmezzomo-source/teste_saisblue/zip/" + commit, zipPath, 30000000);
        using (var sha = SHA256.Create()) using (var stream = File.OpenRead(zipPath)) {
            string actual = BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
            if (actual != hash) throw new UserError("O download não passou na conferência de integridade. O CRM não foi interrompido; tente novamente.");
        }
        report("Download conferido. Preparando a atualização…", 30);
        string unpacked = Path.Combine(folder, "source");
        Directory.CreateDirectory(unpacked);
        string prefix = "teste_saisblue-" + commit + "/";
        long total = 0;
        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        using (var zipStream = File.OpenRead(zipPath)) using (var zip = new ZipArchive(zipStream, ZipArchiveMode.Read)) {
            if (zip.Entries.Count > 5000) throw new UserError("O pacote não tem o formato esperado.");
            foreach (var entry in zip.Entries) {
                if (!entry.FullName.StartsWith(prefix, StringComparison.Ordinal) || entry.FullName.Contains(":") || entry.FullName.Contains("\\") || ((entry.ExternalAttributes >> 16) & 0xF000) == 0xA000) throw new UserError("O pacote contém um caminho inesperado. Nenhum arquivo do CRM foi alterado.");
                string relative = entry.FullName.Substring(prefix.Length);
                if (relative.Split('/').Any(p => p == ".." || p == ".")) throw new UserError("O pacote contém um caminho inválido.");
                string destination = Path.GetFullPath(Path.Combine(unpacked, relative.Replace('/', Path.DirectorySeparatorChar)));
                if (destination != unpacked && !destination.StartsWith(unpacked + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new UserError("O pacote não passou na conferência de segurança.");
                if (!paths.Add(destination)) throw new UserError("O pacote contém arquivos repetidos.");
                total += entry.Length;
                if (total > 200000000) throw new UserError("O pacote excede o tamanho esperado.");
                if (entry.FullName.EndsWith("/")) Directory.CreateDirectory(destination);
                else { Directory.CreateDirectory(Path.GetDirectoryName(destination)); using (var input = entry.Open()) using (var output = File.Create(destination)) input.CopyTo(output); }
            }
        }
        return unpacked;
    }
    internal static void Download(string address, string path, long limit) {
        var uri = new Uri(address);
        for (int redirects = 0; redirects < 5; redirects++) {
            if (uri.Scheme != "https" || !new[] { "github.com", "raw.githubusercontent.com", "codeload.github.com" }.Contains(uri.Host)) throw new UserError("Destino inesperado no download. A atualização foi cancelada.");
            System.Net.ServicePointManager.SecurityProtocol = System.Net.SecurityProtocolType.Tls12;
            var request = (System.Net.HttpWebRequest)System.Net.WebRequest.Create(uri);
            request.CachePolicy = new System.Net.Cache.RequestCachePolicy(System.Net.Cache.RequestCacheLevel.NoCacheNoStore);
            request.AllowAutoRedirect = false; request.Timeout = 30000; request.ReadWriteTimeout = 30000;
            request.UserAgent = "SaisBlueCRM-Updater/1.0";
            using (var response = (System.Net.HttpWebResponse)request.GetResponse()) {
                int status = (int)response.StatusCode;
                if (status >= 300 && status < 400) { uri = new Uri(uri, response.Headers["Location"]); continue; }
                if (status != 200 || response.ContentLength > limit) throw new UserError("O download da atualização não foi concluído.");
                using (var input = response.GetResponseStream()) using (var output = File.Create(path)) {
                    var buffer = new byte[65536]; long total = 0; int n;
                    while ((n = input.Read(buffer, 0, buffer.Length)) > 0) { total += n; if (total > limit) throw new UserError("O download excedeu o tamanho esperado."); output.Write(buffer, 0, n); }
                }
                return;
            }
        }
        throw new UserError("Não consegui concluir o download. Tente novamente.");
    }
    internal static bool Shortcut(string root) {
        try {
            string managed = Path.Combine(Home, "SaisBlue-Atualizador.exe");
            string installed = Path.Combine(root, "desktop", "SaisBlue-Atualizador.exe");
            File.Copy(File.Exists(installed) ? installed : Assembly.GetExecutingAssembly().Location, managed, true);
            File.WriteAllText(Path.Combine(Home, "installation.txt"), root);
            var type = Type.GetTypeFromProgID("WScript.Shell");
            object shell = Activator.CreateInstance(type);
            object link = type.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Sais Blue CRM.lnk") });
            Type t = link.GetType();
            t.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { managed });
            t.InvokeMember("Description", BindingFlags.SetProperty, null, link, new object[] { "Abrir, iniciar, parar e atualizar o Sais Blue CRM" });
            t.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
            return true;
        } catch { return false; }
    }
}

internal sealed class UpdaterForm : Form {
    private readonly TextBox folder = new TextBox(), history = new TextBox();
    private readonly Label status = new Label();
    private readonly ProgressBar progress = new ProgressBar();
    private readonly Button update = new Button(), start = new Button(), stop = new Button(), open = new Button(), browse = new Button(), iphone = new Button();
    private bool busy;
    public UpdaterForm(string hint, string automatic) {
        Text = "Sais Blue CRM"; ClientSize = new Size(680, 550); FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen; Font = new Font("Segoe UI", 10);
        Controls.Add(new Label { Text = "SAIS BLUE CRM", Font = new Font("Segoe UI", 22, FontStyle.Bold), ForeColor = Color.FromArgb(18, 105, 239), AutoSize = true, Left = 24, Top = 20 });
        Controls.Add(new Label { Text = "Atualizações, início automático e recuperação da conexão.", AutoSize = true, Left = 27, Top = 68 });
        Controls.Add(new Label { Text = "Pasta original do CRM no servidor", AutoSize = true, Left = 27, Top = 108 });
        folder.SetBounds(27, 133, 500, 30); folder.Text = Program.Discover(hint);
        browse.Text = "Procurar…"; browse.SetBounds(538, 131, 115, 32);
        browse.Click += delegate { using (var dialog = new FolderBrowserDialog { Description = "Selecione a pasta onde o CRM já está instalado" }) { if (dialog.ShowDialog() == DialogResult.OK) folder.Text = dialog.SelectedPath; } };
        update.Text = "Atualizar e abrir CRM"; update.SetBounds(27, 181, 295, 44); update.BackColor = Color.FromArgb(18,105,239); update.ForeColor = Color.White; update.FlatStyle = FlatStyle.Flat;
        open.Text = "Abrir CRM"; open.SetBounds(338, 181, 315, 44); open.Click += delegate { OpenBrowser(); };
        start.Text = "Iniciar / reconectar"; start.SetBounds(27, 236, 295, 35);
        stop.Text = "Parar CRM"; stop.SetBounds(338, 236, 315, 35);
        update.Click += async delegate { await Run("update"); }; start.Click += async delegate { await Run("start"); }; stop.Click += async delegate { await Run("stop"); };
        iphone.Text = "Configurar iPhone e acesso externo"; iphone.SetBounds(27, 283, 626, 35); iphone.Click += delegate { ConfigureIphone(); };
        progress.SetBounds(27, 340, 626, 20);
        status.SetBounds(27, 372, 626, 52); status.Text = "Confira a pasta e clique em Atualizar. O aplicativo para, faz backup e reinicia automaticamente.";
        history.SetBounds(27, 430, 626, 92); history.Multiline = true; history.ReadOnly = true; history.ScrollBars = ScrollBars.Vertical; history.Font = new Font("Segoe UI", 9);
        Controls.AddRange(new Control[] {folder,browse,update,open,start,stop,iphone,progress,status,history});
        FormClosing += delegate(object sender, FormClosingEventArgs e) { if (busy) { e.Cancel = true; status.Text = "Aguarde a atualização terminar. Você pode minimizar esta janela."; } };
        if (automatic != null) Shown += async delegate { await Run(automatic); };
    }
    private void Report(string message, int value) {
        Action action = delegate { status.Text = message; progress.Value = Math.Max(0, Math.Min(100, value)); history.AppendText(message + Environment.NewLine); };
        if (InvokeRequired) BeginInvoke(action); else action();
    }
    private void ConfigureIphone() {
        string target = folder.Text.Trim();
        if (!Program.IsInstallation(target)) { status.Text = "Selecione a pasta original do CRM."; return; }
        string script = Path.Combine(target, "configurar_iphone.py");
        if (!File.Exists(script)) { status.Text = "Clique primeiro em Atualizar e abrir CRM para instalar esta opção."; return; }
        try {
            Process.Start(new ProcessStartInfo(Path.Combine(target, ".venv", "Scripts", "python.exe"), Program.Quote(script)) { WorkingDirectory = target, UseShellExecute = true });
        } catch { status.Text = "Não consegui abrir o assistente. Atualize o CRM e tente novamente."; }
    }
    private void OpenBrowser() {
        if (!Program.IsInstallation(folder.Text)) { status.Text = "Selecione a pasta original do CRM."; return; }
        try {
            string line = File.ReadLines(Path.Combine(folder.Text, ".env")).FirstOrDefault(l => l.StartsWith("APP_URL="));
            string address = line == null ? "http://127.0.0.1:3000" : line.Substring(8).Trim();
            Uri uri; if (!Uri.TryCreate(address, UriKind.Absolute, out uri) || (uri.Scheme != "http" && uri.Scheme != "https") || uri.UserInfo != "") throw new Exception();
            Process.Start(new ProcessStartInfo(address) {UseShellExecute = true});
        } catch { status.Text = "Não consegui abrir o navegador. Confira o endereço configurado do CRM."; }
    }
    private async Task Run(string action) {
        string target = folder.Text.Trim();
        if (!Program.IsInstallation(target)) { status.Text = "Clique em Procurar e selecione a pasta onde o CRM já funciona."; return; }
        busy = true; update.Enabled = start.Enabled = stop.Enabled = browse.Enabled = iphone.Enabled = folder.Enabled = false; history.Clear();
        try {
            await Task.Run(delegate {
                string source = target;
                if (action == "update" || !File.Exists(Path.Combine(target, "desktop_worker.py"))) source = Program.DownloadPackage(Report);
                string worker = Path.Combine(source, "desktop_worker.py");
                string arguments = Program.Quote(worker) + " --target " + Program.Quote(target) + " --action " + action;
                if (action == "update") arguments += " --source " + Program.Quote(source);
                var info = new ProcessStartInfo(Path.Combine(target, ".venv", "Scripts", "python.exe"), arguments) {
                    WorkingDirectory = source, UseShellExecute = false, CreateNoWindow = true,
                    RedirectStandardOutput = true, RedirectStandardError = true, StandardOutputEncoding = Encoding.UTF8
                };
                string error = null; bool done = false, connectionReady = true; bool? automaticReady = null;
                using (var process = Process.Start(info)) {
                    process.ErrorDataReceived += delegate {}; process.BeginErrorReadLine();
                    string line;
                    while ((line = process.StandardOutput.ReadLine()) != null) {
                        try {
                            var record = Program.Json.Deserialize<Dictionary<string, object>>(line);
                            string message = Convert.ToString(record["message"]);
                            int value = record.ContainsKey("progress") ? Convert.ToInt32(record["progress"]) : 0;
                            Report(message, value);
                            if (record.ContainsKey("event") && Convert.ToString(record["event"]) == "error") error = message;
                            if (record.ContainsKey("event") && Convert.ToString(record["event"]) == "done") done = true;
                            if (record.ContainsKey("connection_ready")) connectionReady = Convert.ToBoolean(record["connection_ready"]);
                            if (record.ContainsKey("automatic_ready")) automaticReady = Convert.ToBoolean(record["automatic_ready"]);
                        } catch {}
                    }
                    process.WaitForExit();
                    if (process.ExitCode != 0 || !done) throw new UserError(error ?? "A operação não foi concluída. Confira a pasta e a permissão da conta Windows.");
                }
                if (Program.Shortcut(target)) Report(action == "stop" ? "CRM parado. O início automático respeitará esta parada. Use Iniciar / reconectar para retomar." : (!connectionReady ? (automaticReady == true ? "CRM iniciado. A conexão WhatsApp ainda não foi confirmada. O monitor tentará reconectar; confira internet e credenciais se persistir." : "CRM iniciado. Conexão WhatsApp e início automático pendentes: clique em Iniciar / reconectar e autorize o Windows.") : automaticReady == true ? "Pronto. Início automático e recuperação ativados. Você pode fechar esta janela; o CRM continuará funcionando e iniciará com o Windows." : "CRM iniciado. Início automático não confirmado: clique em Iniciar / reconectar e autorize o Windows para ativar."), 100);
            });
            if (action != "stop") OpenBrowser();
        } catch (UserError error) { Report(error.Message, 0); }
        catch (System.Net.WebException) { Report("Não consegui baixar a atualização. Confira a internet e tente novamente. O download é conferido antes de parar o CRM.", 0); }
        catch { Report("A operação não foi concluída. Confira a pasta, a conexão e a permissão da conta Windows.", 0); }
        finally { busy = false; update.Enabled = start.Enabled = stop.Enabled = browse.Enabled = iphone.Enabled = folder.Enabled = true; }
    }
}
