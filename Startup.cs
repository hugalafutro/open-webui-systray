namespace OpenWebUiSystray;

static class Startup
{
    internal static bool TryResolveStartUrl(out string startUrl)
    {
        startUrl = "";

        if (AppConfig.TryLoad(out startUrl, out var initial))
            return true;

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
                "Open WebUI Systray",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return false;
        }

        return true;
    }
}
