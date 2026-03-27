namespace OpenWebUiSystray;

static class AppConfig
{
    internal const string FileName = "open-webui-systray.cfg";

    internal static string ConfigPath => Path.Combine(AppContext.BaseDirectory, FileName);

    internal static bool TryLoad(out string url, out string? initialForSetupDialog)
    {
        url = "";
        initialForSetupDialog = null;
        if (!File.Exists(ConfigPath))
            return false;

        foreach (var raw in File.ReadAllLines(ConfigPath))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#'))
                continue;
            if (TryValidateHttpsUrl(line, out var normalized))
            {
                url = normalized;
                return true;
            }

            initialForSetupDialog = line;
            return false;
        }

        return false;
    }

    internal static void Save(string url)
    {
        if (!TryValidateHttpsUrl(url, out var normalized))
            throw new ArgumentException("URL must be a valid https address.", nameof(url));
        File.WriteAllText(ConfigPath, normalized + Environment.NewLine);
    }

    internal static bool TryValidateHttpsUrl(string input, out string normalized)
    {
        normalized = "";
        var trimmed = input.Trim();
        if (trimmed.Length == 0)
            return false;

        if (!Uri.TryCreate(trimmed, UriKind.Absolute, out var uri))
            return false;

        if (!string.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase))
            return false;

        if (string.IsNullOrEmpty(uri.Host))
            return false;

        normalized = uri.AbsoluteUri;
        return true;
    }

    internal static bool ShowUrlSetupDialog(IWin32Window? owner, string? initialText, out string url)
    {
        url = "";
        using var dlg = new UrlSetupForm(initialText ?? "");
        dlg.ShowDialog(owner);

        if (dlg.DialogResult != DialogResult.OK || dlg.AcceptedUrl is null)
            return false;

        url = dlg.AcceptedUrl;
        return true;
    }

    sealed class UrlSetupForm : Form
    {
        private readonly TextBox _urlBox;
        internal string? AcceptedUrl { get; private set; }

        internal UrlSetupForm(string initial)
        {
            Text = "Open WebUI Systray — server address";
            FormBorderStyle = FormBorderStyle.FixedDialog;
            StartPosition = FormStartPosition.CenterScreen;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = true;
            ClientSize = new Size(440, 110);
            Padding = new Padding(12);

            var label = new Label
            {
                AutoSize = true,
                Text = "Enter the HTTPS URL to open (e.g. https://example.com):",
                Location = new Point(12, 12),
            };

            _urlBox = new TextBox
            {
                Location = new Point(12, 36),
                Width = 416,
                Text = initial,
            };

            var ok = new Button
            {
                Text = "OK",
                DialogResult = DialogResult.None,
                Location = new Point(248, 72),
                Width = 88,
            };
            var cancel = new Button
            {
                Text = "Cancel",
                DialogResult = DialogResult.Cancel,
                Location = new Point(340, 72),
                Width = 88,
            };

            AcceptButton = ok;
            CancelButton = cancel;

            ok.Click += (_, _) =>
            {
                if (!TryValidateHttpsUrl(_urlBox.Text, out var normalized))
                {
                    MessageBox.Show(
                        this,
                        "Enter a valid HTTPS URL with a host name (scheme must be https).",
                        Text,
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                    return;
                }

                AcceptedUrl = normalized;
                DialogResult = DialogResult.OK;
                Close();
            };

            Controls.Add(label);
            Controls.Add(_urlBox);
            Controls.Add(ok);
            Controls.Add(cancel);
        }
    }
}
