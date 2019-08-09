using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using System.Security.Cryptography;
using System.Text;

namespace QuimiOSWebForms.Pages;

public class LoginModel : PageModel
{
    [BindProperty]
    public string? Username { get; set; }
    
    [BindProperty]
    public string? Password { get; set; }
    
    public string ViewState { get; set; } = "";
    public string ViewStateGenerator { get; set; } = "";
    public string EventValidation { get; set; } = "";
    public string? ErrorMessage { get; set; }
    
    private static readonly string VALID_USER = "demo_user";
    private static readonly string VALID_PASS = "demo_pass";
    
    public void OnGet()
    {
        GenerateViewState();
    }
    
    public IActionResult OnPost()
    {
        GenerateViewState();
        
        if (Username == VALID_USER && Password == VALID_PASS)
        {
            // Store auth in session
            HttpContext.Session.SetString("Authenticated", "true");
            HttpContext.Session.SetString("User", Username ?? "");
            HttpContext.Session.SetInt32("ClientId", 101);
            
            return RedirectToPage("/Consulta");
        }
        
        ErrorMessage = "Usuario o contraseña incorrectos";
        return Page();
    }
    
    private void GenerateViewState()
    {
        // Generate encrypted-like state (simplified for mock)
        var timestamp = DateTime.UtcNow.Ticks.ToString();
        
        // Create a base64 encoded state that looks like ASP.NET
        var stateData = $"Page=Login|Timestamp={timestamp}";
        ViewState = Convert.ToBase64String(Encoding.UTF8.GetBytes(stateData));
        
        // ViewStateGenerator (shorter, like ASP.NET)
        var vsgData = $"Generator={(timestamp.GetHashCode() % 10000)}";
        ViewStateGenerator = Convert.ToBase64String(Encoding.UTF8.GetBytes(vsgData))[..20];
        
        // EventValidation (random token)
        var validationData = new byte[32];
        RandomNumberGenerator.Fill(validationData);
        EventValidation = Convert.ToBase64String(validationData);
        
        // Store in session for validation
        HttpContext.Session.SetString("ViewState", ViewState);
        HttpContext.Session.SetString("EventValidation", EventValidation);
    }
}