namespace WebSystray;

static class Startup
{
    internal static bool TryResolveStartUrl(out string startUrl)
    {
        startUrl = "";

        if (AppConfig.TryLoad(out startUrl))
            return true;

        string? initial = null;
        if (File.Exists(AppConfig.ConfigPath))
        {
            initial = File.ReadAllLines(AppConfig.ConfigPath)
                .Select(static l => l.Trim())
                .FirstOrDefault(static l => l.Length > 0 && !l.StartsWith('#'));
        }

        if (!AppConfig.ShowUrlSetupDialog(owner: null, initial, out startUrl))
            return false;

        try
        {
            AppConfig.Save(startUrl);
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                null,
                $"Could not save configuration file:\n{ex.Message}",
                "Web Systray",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return false;
        }

        return true;
    }
}
