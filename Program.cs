using System.Windows.Forms;

namespace OpenWebUiSystray;

static class Program
{
    private const string SingleInstanceMutexName = @"Local\OpenWebUiSystray-single-instance";

    [STAThread]
    static void Main()
    {
        using var instanceMutex = new Mutex(true, SingleInstanceMutexName, out bool createdNew);
        if (!createdNew)
            return;

        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        ApplicationConfiguration.Initialize();

        if (!Startup.TryResolveStartUrl(out var startUrl))
            return;

        Application.Run(new TrayApplicationContext(startUrl));
    }
}
