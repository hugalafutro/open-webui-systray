namespace WebSystray;

static class Program
{
    private const string SingleInstanceMutexName = @"Local\WebSystray-open-webui-desktop";

    [STAThread]
    static void Main()
    {
        using var instanceMutex = new Mutex(true, SingleInstanceMutexName, out bool createdNew);
        if (!createdNew)
            return;

        ApplicationConfiguration.Initialize();
        Application.Run(new TrayApplicationContext());
    }
}
