using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using System.Security.Cryptography;
using System.Text;

namespace QuimiOSWebForms.Pages;

public class LoginModel : PageModel
{
    [BindProperty]
    public string? Login1_UserName { get; set; }
    
    [BindProperty]
    public string? Login1_Password { get; set; }
    
    [BindProperty]
    public string? Login1_LoginButton { get; set; }
    
    public string ViewState { get; set; } = "";
    public string ViewStateGenerator { get; set; } = "";
    public string EventValidation { get; set; } = "";
    public string? ErrorMessage { get; set; }
    
    private const string VALID_USER = "demo_user";
    private const string VALID_PASS = "demo_pass";
    
    public void OnGet()
    {
        GenerateViewState();
    }
    
    public IActionResult OnPost()
    {
        GenerateViewState();
        
        if (Login1_UserName == VALID_USER && Login1_Password == VALID_PASS)
        {
            HttpContext.Session.SetString("Authenticated", "true");
            HttpContext.Session.SetString("User", Login1_UserName ?? "");
            HttpContext.Session.SetInt32("ClientId", 101);
            HttpContext.Session.SetString("SessionToken", GenerateSessionToken());
            
            return RedirectToPage("/Consulta");
        }
        
        ErrorMessage = "Usuario o contraseña incorrectos";
        return Page();
    }
    
    private void GenerateViewState()
    {
        var timestamp = DateTime.UtcNow.Ticks.ToString();
        var stateData = $"Page=Login|Timestamp={timestamp}|Session={HttpContext.Session.Id}";
        ViewState = Convert.ToBase64String(Encoding.UTF8.GetBytes(stateData));
        
        var vsgData = $"Generator={timestamp.GetHashCode() % 10000}";
        ViewStateGenerator = Convert.ToBase64String(Encoding.UTF8.GetBytes(vsgData))[..20];
        
        // EventValidation for allowed events on this page
        var allowedEvents = $"/Login:btnLogin|{timestamp}";
        EventValidation = Convert.ToBase64String(Encoding.UTF8.GetBytes(allowedEvents));
    }
    
    private string GenerateSessionToken()
    {
        var tokenData = $"{HttpContext.Session.Id}|{DateTime.UtcNow.Ticks}";
        return Convert.ToBase64String(Encoding.UTF8.GetBytes(tokenData));
    }
}