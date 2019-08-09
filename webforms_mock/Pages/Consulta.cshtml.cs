using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using System.Security.Cryptography;
using System.Text;

namespace QuimiOSWebForms.Pages;

public class ConsultaModel : PageModel
{
    [BindProperty(SupportsGet = true)]
    public int ClientId { get; set; } = 101;
    
    [BindProperty(SupportsGet = true)]
    public int PageNum { get; set; } = 1;
    
    [BindProperty]
    public string? TxtCliente { get; set; }
    
    public List<SampleRecord> Records { get; set; } = new();
    public int TotalPages { get; set; } = 3;
    public int CurrentPage { get; set; } = 1;
    
    public string ViewState { get; set; } = "";
    public string ViewStateGenerator { get; set; } = "";
    public string EventValidation { get; set; } = "";
    
    // Sample data
    private static readonly List<SampleRecord> AllRecords = new()
    {
        new() { Fecha = "20/03/2023 12:00:00 AM", Recep = "20/03/2023 01:18:00 AM", Folio = "100002", Cliente = "105", Paciente = "387", EstPer = "168", Test = "Glucose", FecCapRes = "20/03/2023 09:18:00 AM", FecLibera = "20/03/2023 02:18:00 PM", SucProc = "Branch C", Maquilador = "LabCorp", Priority = "Stat", FecNac = "21/11/1979" },
        new() { Fecha = "19/03/2023 09:00:00 PM", Recep = "19/03/2023 09:32:00 PM", Folio = "100003", Cliente = "104", Paciente = "831", EstPer = "435", Test = "CBC", FecCapRes = "20/03/2023 01:32:00 AM", FecLibera = "21/03/2023 01:32:00 AM", SucProc = "Lab East", Maquilador = "Quest Labs", Priority = "Stat", FecNac = "10/06/1984" },
        new() { Fecha = "19/03/2023 06:00:00 PM", Recep = "19/03/2023 07:18:00 PM", Folio = "100004", Cliente = "104", Paciente = "997", EstPer = "706", Test = "Lipid Panel", FecCapRes = "20/03/2023 01:18:00 AM", FecLibera = "20/03/2023 11:18:00 PM", SucProc = "Lab East", Maquilador = "Quest Labs", Priority = "Routine", FecNac = "11/07/1954" },
        new() { Fecha = "19/03/2023 01:00:00 PM", Recep = "19/03/2023 01:37:00 PM", Folio = "100005", Cliente = "104", Paciente = "417", EstPer = "901", Test = "Chemistry Panel", FecCapRes = "19/03/2023 05:37:00 PM", FecLibera = "20/03/2023 12:37:00 AM", SucProc = "Lab North", Maquilador = "Maq X", Priority = "Stat", FecNac = "10/10/1978" },
        new() { Fecha = "19/03/2023 11:00:00 AM", Recep = "19/03/2023 12:27:00 PM", Folio = "100006", Cliente = "103", Paciente = "347", EstPer = "673", Test = "Blood Test", FecCapRes = "19/03/2023 04:27:00 PM", FecLibera = "20/03/2023 01:27:00 AM", SucProc = "Branch C", Maquilador = "Quest Labs", Priority = "Normal", FecNac = "04/03/1971" },
        new() { Fecha = "19/03/2023 08:00:00 AM", Recep = "19/03/2023 08:48:00 AM", Folio = "100007", Cliente = "101", Paciente = "416", EstPer = "224", Test = "Glucose", FecCapRes = "19/03/2023 10:48:00 AM", FecLibera = "20/03/2023 09:48:00 AM", SucProc = "Lab East", Maquilador = "Quest Labs", Priority = "Normal", FecNac = "27/06/1991" },
        new() { Fecha = "19/03/2023 05:00:00 AM", Recep = "19/03/2023 05:41:00 AM", Folio = "100008", Cliente = "105", Paciente = "459", EstPer = "551", Test = "Blood Test", FecCapRes = "19/03/2023 09:41:00 AM", FecLibera = "19/03/2023 01:41:00 PM", SucProc = "Branch B", Maquilador = "Maq X", Priority = "Stat", FecNac = "12/02/1990" },
        new() { Fecha = "19/03/2023 01:00:00 AM", Recep = "19/03/2023 01:34:00 AM", Folio = "100009", Cliente = "104", Paciente = "356", EstPer = "645", Test = "Hemogram", FecCapRes = "19/03/2023 05:34:00 AM", FecLibera = "20/03/2023 04:34:00 AM", SucProc = "Lab North", Maquilador = "Maq Y", Priority = "Routine", FecNac = "01/03/1970" },
        new() { Fecha = "19/03/2023 12:00:00 AM", Recep = "19/03/2023 12:58:00 AM", Folio = "100010", Cliente = "105", Paciente = "773", EstPer = "184", Test = "Chemistry Panel", FecCapRes = "19/03/2023 04:58:00 AM", FecLibera = "19/03/2023 10:58:00 AM", SucProc = "Lab East", Maquilador = "Maq Y", Priority = "Routine", FecNac = "25/07/1998" },
        new() { Fecha = "18/03/2023 09:00:00 PM", Recep = "18/03/2023 09:47:00 PM", Folio = "100011", Cliente = "102", Paciente = "879", EstPer = "166", Test = "Lipid Panel", FecCapRes = "19/03/2023 03:47:00 AM", FecLibera = "19/03/2023 06:47:00 PM", SucProc = "Branch A", Maquilador = "Quest Labs", Priority = "Stat", FecNac = "09/09/1980" },
    };
    
    public void OnGet()
    {
        // Check auth
        var auth = HttpContext.Session.GetString("Authenticated");
        if (auth != "true")
        {
            Response.Redirect("/Login");
            return;
        }
        
        // Update client from query or session
        ClientId = HttpContext.Session.GetInt32("ClientId") ?? 101;
        CurrentPage = PageNum > 0 ? PageNum : 1;
        
        LoadRecords();
        GenerateViewState();
    }
    
    public IActionResult OnPost()
    {
        var auth = HttpContext.Session.GetString("Authenticated");
        if (auth != "true")
        {
            return RedirectToPage("/Login");
        }
        
        // Handle client search
        if (!string.IsNullOrEmpty(TxtCliente) && int.TryParse(TxtCliente, out int newClient))
        {
            ClientId = newClient;
            HttpContext.Session.SetInt32("ClientId", ClientId);
            CurrentPage = 1;
        }
        
        LoadRecords();
        GenerateViewState();
        
        return Page();
    }
    
    private void LoadRecords()
    {
        int rowsPerPage = 10;
        int startIdx = (CurrentPage - 1) * rowsPerPage;
        
        var filtered = AllRecords.Where(r => r.Cliente == ClientId.ToString()).ToList();
        if (!filtered.Any())
            filtered = AllRecords; // Show all if no match
        
        var paged = filtered.Skip(startIdx).Take(rowsPerPage).ToList();
        
        // Add row numbers
        for (int i = 0; i < paged.Count; i++)
        {
            paged[i].RowNum = startIdx + i + 2; // +2 because grid starts at row 2
        }
        
        Records = paged;
        TotalPages = (int)Math.Ceiling((double)filtered.Count / rowsPerPage);
        if (TotalPages < 1) TotalPages = 1;
    }
    
    private void GenerateViewState()
    {
        var timestamp = DateTime.UtcNow.Ticks.ToString();
        var stateData = $"Page=Consulta|Client={ClientId}|PageNum={CurrentPage}|Timestamp={timestamp}";
        ViewState = Convert.ToBase64String(Encoding.UTF8.GetBytes(stateData));
        
        var vsgData = $"Generator={(timestamp.GetHashCode() % 10000)}";
        ViewStateGenerator = Convert.ToBase64String(Encoding.UTF8.GetBytes(vsgData))[..20];
        
        var validationData = new byte[32];
        RandomNumberGenerator.Fill(validationData);
        EventValidation = Convert.ToBase64String(validationData);
    }
}

public class SampleRecord
{
    public int RowNum { get; set; }
    public string Fecha { get; set; } = "";
    public string Recep { get; set; } = "";
    public string Folio { get; set; } = "";
    public string Cliente { get; set; } = "";
    public string Paciente { get; set; } = "";
    public string EstPer { get; set; } = "";
    public string Test { get; set; } = "";
    public string FecCapRes { get; set; } = "";
    public string FecLibera { get; set; } = "";
    public string SucProc { get; set; } = "";
    public string Maquilador { get; set; } = "";
    public string Priority { get; set; } = "";
    public string FecNac { get; set; } = "";
}