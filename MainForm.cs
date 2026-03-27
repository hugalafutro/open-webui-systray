using Microsoft.Web.WebView2.WinForms;

namespace OpenWebUiSystray;

sealed class MainForm : Form
{
    private readonly WebView2 _webView;
    private readonly string _startUrl;

    public MainForm(string startUrl)
    {
        _startUrl = startUrl;
        Text = "Open WebUI Systray";
        Size = new System.Drawing.Size(1280, 800);
        StartPosition = FormStartPosition.Manual;
        var wa = (Screen.PrimaryScreen ?? Screen.AllScreens[0]).WorkingArea;
        Location = new System.Drawing.Point(wa.Right - Width, wa.Bottom - Height);
        BackColor = Color.Black;

        _webView = new WebView2
        {
            Dock = DockStyle.Fill,
            DefaultBackgroundColor = Color.Black,
        };
        Controls.Add(_webView);
    }

    protected override async void OnLoad(EventArgs e)
    {
        base.OnLoad(e);

        var dataDir = Path.Combine(AppContext.BaseDirectory, "WebView2Data");
        var env = await Microsoft.Web.WebView2.Core.CoreWebView2Environment.CreateAsync(
            userDataFolder: dataDir);

        await _webView.EnsureCoreWebView2Async(env);
        _webView.CoreWebView2.Settings.IsZoomControlEnabled = false;
        _webView.ZoomFactor = 0.9;
        _webView.CoreWebView2.Navigate(_startUrl);
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (e.CloseReason == CloseReason.UserClosing)
        {
            e.Cancel = true;
            Hide();
            return;
        }
        base.OnFormClosing(e);
    }
}
