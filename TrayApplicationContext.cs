using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;

namespace OpenWebUiSystray;

sealed class TrayApplicationContext : ApplicationContext
{
    private readonly NotifyIcon _trayIcon;
    private readonly string _startUrl;
    private MainForm? _mainForm;

    public TrayApplicationContext(string startUrl)
    {
        _startUrl = startUrl;

        var quitItem = new ToolStripMenuItem("Quit", null, (_, _) => Application.Exit());
        var contextMenu = new ContextMenuStrip();
        contextMenu.Items.Add(quitItem);

        _trayIcon = new NotifyIcon
        {
            Icon = GenerateIcon(),
            Text = "Open WebUI Systray",
            ContextMenuStrip = contextMenu,
            Visible = true
        };

        _trayIcon.MouseClick += OnTrayClick;
    }

    private void OnTrayClick(object? sender, MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left) return;

        if (_mainForm == null || _mainForm.IsDisposed)
        {
            _mainForm = new MainForm(_startUrl) { Icon = _trayIcon.Icon };
        }

        _mainForm.Show();
        _mainForm.WindowState = FormWindowState.Normal;
        _mainForm.BringToFront();
        _mainForm.Activate();
    }

    private static Icon GenerateIcon()
    {
        const int size = 32;
        using var bmp = new Bitmap(size, size);
        using var g = Graphics.FromImage(bmp);

        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
        g.Clear(Color.Transparent);

        var rect = new Rectangle(2, 2, size - 4, size - 4);
        using var path = RoundedRect(rect, 6);
        using (var brush = new SolidBrush(Color.White))
            g.FillPath(brush, path);

        using var font = new Font("Segoe UI", 14f, FontStyle.Bold, GraphicsUnit.Pixel);
        const string text = "OI";
        var textSize = g.MeasureString(text, font);
        float x = (size - textSize.Width) / 2f;
        float y = (size - textSize.Height) / 2f;
        using (var brush = new SolidBrush(Color.FromArgb(30, 30, 30)))
            g.DrawString(text, font, brush, x, y);

        return System.Drawing.Icon.FromHandle(bmp.GetHicon());
    }

    private static GraphicsPath RoundedRect(Rectangle bounds, int radius)
    {
        int d = radius * 2;
        var path = new GraphicsPath();
        path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
        path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
        path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
        path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _trayIcon.Visible = false;
            _trayIcon.Dispose();
            _mainForm?.Close();
            _mainForm?.Dispose();
        }
        base.Dispose(disposing);
    }
}
