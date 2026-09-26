using System.Collections.Concurrent;
using System.Net;
using System.Net.Http.Headers;
using System.Text.Json;

namespace TableTennisLive.Core.Services;

public static class JsonFields
{
    public static JsonElement At(this JsonElement element, string property) =>
        element.ValueKind == JsonValueKind.Object && element.TryGetProperty(property, out var value)
            ? value : default;

    public static IEnumerable<JsonElement> Items(this JsonElement element) =>
        element.ValueKind == JsonValueKind.Array ? element.EnumerateArray() : [];

    public static string Text(this JsonElement element) => element.ValueKind switch
    {
        JsonValueKind.String => element.GetString() ?? "",
        JsonValueKind.Number => element.GetRawText(),
        _ => ""
    };

    public static int Number(this JsonElement element) => int.TryParse(element.Text(), out var value) ? value : 0;

    public static bool Flag(this JsonElement element) => element.ValueKind == JsonValueKind.True;
}

public sealed class OfficialJson : IDisposable
{
    private readonly HttpClient _http;
    private readonly ConcurrentDictionary<string, (JsonElement Value, DateTimeOffset Time)> _cache = new();

    public OfficialJson()
    {
        var handler = new HttpClientHandler
        {
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate | DecompressionMethods.Brotli,
            AllowAutoRedirect = true
        };
        _http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(15) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (Windows NT 10.0; Win64; x64)");
        _http.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
    }

    public async Task<JsonElement> GetAsync(string url, string key, TimeSpan ttl,
        CancellationToken cancellationToken, bool revalidate = true)
    {
        if (_cache.TryGetValue(key, out var cached) && DateTimeOffset.UtcNow - cached.Time < ttl)
            return cached.Value;
        var uri = revalidate
            ? url + (url.Contains('?') ? '&' : '?') + "_refresh=" +
              (DateTimeOffset.UtcNow.ToUnixTimeSeconds() / Math.Max(2, Math.Min((long)ttl.TotalSeconds, 120)))
            : url;
        using var request = new HttpRequestMessage(HttpMethod.Get, uri);
        request.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true };
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead,
            cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        if (response.Content.Headers.ContentType?.MediaType?.Contains("json", StringComparison.OrdinalIgnoreCase) != true)
            throw new InvalidDataException("官方接口没有返回 JSON");
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        var value = document.RootElement.Clone();
        _cache[key] = (value, DateTimeOffset.UtcNow);
        return value;
    }

    public void Evict(string key) => _cache.TryRemove(key, out _);
    public void Dispose() => _http.Dispose();
}
