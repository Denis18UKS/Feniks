using System.Diagnostics;
using System.Text.Json;

// Line-delimited JSON bridge. Only explicitly allowed, non-destructive operations belong here.
var allowedApps = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
{
    ["notepad"] = "notepad.exe",
    ["calculator"] = "calc.exe"
};

string? line;
while ((line = Console.ReadLine()) is not null)
{
    BridgeResponse response;
    try
    {
        var request = JsonSerializer.Deserialize<BridgeRequest>(line);
        response = request?.Command switch
        {
            "ping" => new(true, "bridge.ready", new { version = "0.1.0", platform = "windows" }),
            "list_windows" => new(true, "windows.listed", Process.GetProcesses()
                .Where(p => p.MainWindowHandle != IntPtr.Zero)
                .Select(p => new { id = p.Id, title = p.MainWindowTitle }).Take(100)),
            "open_approved_app" when request.Arg is not null && allowedApps.TryGetValue(request.Arg, out var app)
                => StartApproved(app),
            _ => new(false, "command.denied", new { reason = "Command is not allow-listed" })
        };
    }
    catch (Exception error)
    {
        response = new(false, "bridge.error", new { type = error.GetType().Name, message = error.Message });
    }
    Console.WriteLine(JsonSerializer.Serialize(response));
}

static BridgeResponse StartApproved(string app)
{
    Process.Start(new ProcessStartInfo(app) { UseShellExecute = true });
    return new(true, "application.started", new { application = app });
}

internal record BridgeRequest(string Command, string? Arg);
internal record BridgeResponse(bool Ok, string Event, object Data);
