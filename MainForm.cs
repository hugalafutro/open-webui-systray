using Microsoft.Web.WebView2.WinForms;

namespace WebSystray;

sealed class MainForm : Form
{
    private readonly WebView2 _webView;

    public MainForm()
    {
        Text = "open-webui-desktop";
        Size = new System.Drawing.Size(1280, 800);
        StartPosition = FormStartPosition.Manual;
        var wa = (Screen.PrimaryScreen ?? Screen.AllScreens[0]).WorkingArea;
        Location = new System.Drawing.Point(wa.Right - Width, wa.Bottom - Height);

        _webView = new WebView2 { Dock = DockStyle.Fill };
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
        _webView.CoreWebView2.Navigate("https://ai.zmrd.uk");
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
