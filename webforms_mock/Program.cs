using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.AspNetCore.Http.Features;

var builder = WebApplication.CreateBuilder(args);

builder.WebHost.ConfigureKestrel(options =>
{
    options.Limits.MaxRequestBodySize = 1024 * 1024 * 10;
    options.Limits.MinRequestBodyDataRate = null;
    options.Limits.MinResponseDataRate = null;
});

builder.Services.AddDistributedMemoryCache();
builder.Services.AddSession(options =>
{
    options.IdleTimeout = TimeSpan.FromMinutes(30);
    options.Cookie.HttpOnly = true;
    options.Cookie.IsEssential = true;
    options.Cookie.SameSite = SameSiteMode.Lax;
});

// Add Antiforgery but with relaxed settings
builder.Services.AddAntiforgery(options =>
{
    options.SuppressXFrameOptionsHeader = true;
    options.Cookie.Name = "MockAntiforgery";
    options.Cookie.SameSite = SameSiteMode.Lax;
});

builder.Services.AddRazorPages();

builder.Services.Configure<FormOptions>(options =>
{
    options.MultipartBodyLengthLimit = 1024 * 1024 * 10;
    options.ValueLengthLimit = 1024 * 1024 * 10;
});

var app = builder.Build();

app.UseStaticFiles();
app.UseSession();

app.MapRazorPages();

app.Run();