using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using System.Security.Cryptography;
using System.Text;

namespace QuimiOSWebForms.Pages;

public class WorkOrderRecord
{
    public string Fecha { get; set; } = "";
    public string FechaRecep { get; set; } = "";
    public int Folio { get; set; }
    public int Cliente { get; set; }
    public int Paciente { get; set; }
    public int EstPer { get; set; }
    public string Prueba { get; set; } = "";
    public string FecCapRes { get; set; } = "";
    public string FecLibera { get; set; } = "";
    public string SucProc { get; set; } = "";
    public string Maquilador { get; set; } = "";
    public string Prioridad { get; set; } = "";
    public string FecNac { get; set; } = "";
}

public class ConsultaModel : PageModel
{
    private const int PageSize = 10;
    private const int TotalRecords = 100;
    private static readonly string[] Pruebas = { "Glucose", "CBC", "Lipid Panel", "Chemistry Panel", "Blood Test", "Hemogram" };
    private static readonly string[] Sucursales = { "Lab East", "Lab North", "Branch A", "Branch B", "Branch C" };
    private static readonly string[] Maquiladores = { "Quest Labs", "LabCorp", "Maq X", "Maq Y" };
    private static readonly string[] Prioridades = { "Stat", "Routine", "Normal" };
    
    public int CurrentPage { get; set; } = 1;
    public int TotalPages { get; set; } = 10;
    public List<WorkOrderRecord> Records { get; set; } = new();
    public string LoggedInUser { get; set; } = "";
    public int ClientId { get; set; } = 101;
    
    public string ViewState { get; set; } = "";
    public string ViewStateGenerator { get; set; } = "";
    public string EventValidation { get; set; } = "";
    
    public IActionResult OnGet()
    {
        if (!IsAuthenticated())
            return RedirectToPage("/Login");
        
        LoggedInUser = HttpContext.Session.GetString("User") ?? "101";
        ClientId = HttpContext.Session.GetInt32("ClientId") ?? 101;
        
        if (int.TryParse(Request.Query["page"], out var page))
            CurrentPage = Math.Max(1, Math.Min(page, TotalPages));
        
        GenerateViewState();
        GenerateRecords();
        
        return Page();
    }
    
    public IActionResult OnPost()
    {
        if (!IsAuthenticated())
            return RedirectToPage("/Login");
        
        LoggedInUser = HttpContext.Session.GetString("User") ?? "101";
        ClientId = HttpContext.Session.GetInt32("ClientId") ?? 101;
        
        // Handle search button
        if (Request.Form.ContainsKey("ctl00_ContentMasterPage_btnBuscar"))
        {
            if (int.TryParse(Request.Form["ctl00_ContentMasterPage_txtcliente"], out var client))
                ClientId = client;
            CurrentPage = 1;
        }
        
        GenerateViewState();
        GenerateRecords();
        
        return Page();
    }
    
    private bool IsAuthenticated()
    {
        return HttpContext.Session.GetString("Authenticated") == "true";
    }
    
    private void GenerateViewState()
    {
        var timestamp = DateTime.UtcNow.Ticks.ToString();
        var stateData = $"Page=Consulta|CurrentPage={CurrentPage}|ClientId={ClientId}|Timestamp={timestamp}";
        ViewState = Convert.ToBase64String(Encoding.UTF8.GetBytes(stateData));
        
        var vsgData = $"Generator={timestamp.GetHashCode() % 10000}";
        ViewStateGenerator = Convert.ToBase64String(Encoding.UTF8.GetBytes(vsgData))[..20];
        
        // EventValidation for pagination and search
        var allowedEvents = $"/Consulta:btnBuscar|/Consulta:lnkNext|/Consulta:lnkPrev|Page={CurrentPage}";
        EventValidation = Convert.ToBase64String(Encoding.UTF8.GetBytes(allowedEvents));
    }
    
    private void GenerateRecords()
    {
        var random = new Random(CurrentPage * 1000 + ClientId);
        var startIndex = (CurrentPage - 1) * PageSize;
        var baseDate = new DateTime(2023, 03, 20);
        
        for (int i = 0; i < PageSize; i++)
        {
            var recordIndex = startIndex + i;
            var fecha = baseDate.AddHours(-recordIndex * 3);
            var fechaRecep = fecha.AddMinutes(random.Next(30, 90));
            var fecCapRes = fechaRecep.AddHours(random.Next(2, 8));
            var fecLibera = fecCapRes.AddHours(random.Next(4, 12));
            
            Records.Add(new WorkOrderRecord
            {
                Fecha = fecha.ToString("dd/MM/yyyy hh:mm:ss tt"),
                FechaRecep = fechaRecep.ToString("dd/MM/yyyy hh:mm:ss tt"),
                Folio = 100002 + recordIndex,
                Cliente = 101 + random.Next(0, 5),
                Paciente = 300 + random.Next(100, 900),
                EstPer = 100 + random.Next(100, 900),
                Prueba = Pruebas[random.Next(Pruebas.Length)],
                FecCapRes = fecCapRes.ToString("dd/MM/yyyy hh:mm:ss tt"),
                FecLibera = fecLibera.ToString("dd/MM/yyyy hh:mm:ss tt"),
                SucProc = Sucursales[random.Next(Sucursales.Length)],
                Maquilador = Maquiladores[random.Next(Maquiladores.Length)],
                Prioridad = Prioridades[random.Next(Prioridades.Length)],
                FecNac = new DateTime(1970 + random.Next(0, 35), random.Next(1, 13), random.Next(1, 29))
                    .ToString("dd/MM/yyyy")
            });
        }
    }
}