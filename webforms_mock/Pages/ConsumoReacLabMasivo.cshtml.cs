using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using System.Security.Cryptography;
using System.Text;

namespace QuimiOSWebForms.Pages;

public class ReagentGridRecord
{
    public string ReagentCode { get; set; } = "";
    public int ProductId { get; set; }
    public decimal Stock { get; set; }
    public int Pacientes { get; set; }
    public int Repeticiones { get; set; }
    public int Control { get; set; }
    public int Calibracion { get; set; }
    public int Cancelacion { get; set; }
    public string MotivoCancelacion { get; set; } = "";
    public int Validacion { get; set; }
    public int SinIdentificar { get; set; }
    public bool QueProveedor { get; set; }
    public int Activo { get; set; } = 1;
    public int CalcAuto { get; set; } = 1;
}

public class ConsumoReacLabMasivoModel : PageModel
{
    public string ViewState { get; set; } = "";
    public string ViewStateGenerator { get; set; } = "";
    public string EventValidation { get; set; } = "";
    public string HfActivo { get; set; } = "0";
    public string HfCalcAuto { get; set; } = "1";
    public string FechaDesde { get; set; } = DateTime.Now.AddDays(-7).ToString("dd/MM/yyyy");
    public string FechaHasta { get; set; } = DateTime.Now.ToString("dd/MM/yyyy");
    public string LoggedInUser { get; set; } = "";
    public string? ErrorMessage { get; set; }
    public string? SuccessMessage { get; set; }
    public List<ReagentGridRecord> Records { get; set; } = new();

    // All 61 reagent codes from quimios-names.js
    private static readonly string[] ReagentCodes = {
        "ACVALPMT", "AFP_MTY", "BHCGMTY", "CA125MTY", "CA153MTY", "CA199MTY", "CEA2MTY",
        "CORSMTY", "E2MTY", "FERR_MTY", "FSHMTY", "INSULMTY", "LHMTY", "PROGMTY", "PROLMTY",
        "PSALIBMT", "PSATOTMT", "TETOTMTY", "TSHMTY", "TUMTY", "T3LIBMTY", "T3TOTMTY",
        "T4LIBMTY", "T4TOTMTY", "ACURIMTY", "ALBMTY", "AMIMTY", "BILIDMTY", "BILITMTY",
        "CA-SMTY", "CLOMTY", "COLHMTY", "COLTMTY", "CREAMTY", "C3_MTY", "C4_MTY",
        "DHLMTY", "FESMTY", "FOSFAMTY", "FOSFMTY", "GGTPMTY", "GLUMTY", "IgA_MTY",
        "IgG_MTY", "IgM_MTY", "IgE_MTY", "LIPASAMT", "MGSMTY", "NITROMTY", "PCRCUMTY",
        "PCRULMTY", "POTMTY", "PRTTSMTY", "SODMTY", "TGOMTY", "TGPMTY", "TRF_MTY",
        "TRIGLMTY", "UIBCMTY", "HBGLMTY", "DIMEMTY"
    };

    public IActionResult OnGet()
    {
        if (!IsAuthenticated())
            return RedirectToPage("/Login");

        LoggedInUser = HttpContext.Session.GetString("User") ?? "demo_user";
        GenerateViewState();
        GenerateRecords();
        return Page();
    }

    public IActionResult OnPost()
    {
        if (!IsAuthenticated())
            return RedirectToPage("/Login");

        LoggedInUser = HttpContext.Session.GetString("User") ?? "demo_user";
        GenerateViewState();

        // Handle search button
        if (Request.Form.ContainsKey("ctl00$ContentMasterPage$btnBuscarEstudio"))
        {
            GenerateRecords();
            return Page();
        }

        // Handle save button
        if (Request.Form.ContainsKey("ctl00$ContentMasterPage$btnGuardaMasivo"))
        {
            var validationErrors = ValidateAndSave();
            if (validationErrors.Count > 0)
            {
                ErrorMessage = string.Join("; ", validationErrors);
                GenerateRecords(); // Re-generate to show current state
                return Page();
            }

            SuccessMessage = "Consumos guardados correctamente";
            GenerateRecords();
            return Page();
        }

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
        var stateData = $"Page=ConsumoReacLabMasivo|Timestamp={timestamp}|Session={HttpContext.Session.Id}";
        ViewState = Convert.ToBase64String(Encoding.UTF8.GetBytes(stateData));

        var vsgData = $"Generator={timestamp.GetHashCode() % 10000}";
        ViewStateGenerator = Convert.ToBase64String(Encoding.UTF8.GetBytes(vsgData))[..20];

        var allowedEvents = $"/Inventarios/ConsumoReacLabMasivo:btnBuscarEstudio|/Inventarios/ConsumoReacLabMasivo:btnGuardaMasivo|{timestamp}";
        EventValidation = Convert.ToBase64String(Encoding.UTF8.GetBytes(allowedEvents));
    }

    private void GenerateRecords()
    {
        var random = new Random(42); // Fixed seed for reproducibility
        var stockBase = new Dictionary<string, decimal>
        {
            ["GLUMTY"] = 100, ["TSHMTY"] = 50, ["CREAMTY"] = 75, ["COLHMTY"] = 60,
            ["COLTMTY"] = 80, ["AMIMTY"] = 45, ["FERR_MTY"] = 30, ["TETOTMTY"] = 55,
            ["PSATOTMT"] = 40, ["BHCGMTY"] = 35, ["CA125MTY"] = 25, ["HBGLMTY"] = 70,
            ["DIMEMTY"] = 20, ["TUMTY"] = 50, ["TGOMTY"] = 65, ["TGPMTY"] = 55,
            ["DHLMTY"] = 40, ["C3_MTY"] = 35, ["C4_MTY"] = 35, ["IgG_MTY"] = 45,
            ["IgM_MTY"] = 45, ["IgE_MTY"] = 40, ["PCRCUMTY"] = 60, ["TRIGLMTY"] = 80,
            ["FOSFAMTY"] = 25, ["GGTPMTY"] = 55, ["MGSMTY"] = 30, ["NITROMTY"] = 50,
            ["FESMTY"] = 40, ["UIBCMTY"] = 35, ["TRF_MTY"] = 45, ["LIPASAMT"] = 30,
            ["ACURIMTY"] = 25, ["ALBMTY"] = 70, ["BILIDMTY"] = 45, ["BILITMTY"] = 50,
            ["CA-SMTY"] = 40, ["CLOMTY"] = 60, ["FOSFMTY"] = 50, ["PRTTSMTY"] = 55,
            ["SODMTY"] = 60, ["POTMTY"] = 60, ["ACVALPMT"] = 25, ["AFP_MTY"] = 30,
            ["CA153MTY"] = 20, ["CA199MTY"] = 20, ["CEA2MTY"] = 30, ["CORSMTY"] = 35,
            ["E2MTY"] = 25, ["FSHMTY"] = 30, ["INSULMTY"] = 40, ["LHMTY"] = 30,
            ["PROGMTY"] = 20, ["PROLMTY"] = 20, ["PSALIBMT"] = 20, ["T3LIBMTY"] = 35,
            ["T3TOTMTY"] = 35, ["T4LIBMTY"] = 35, ["T4TOTMTY"] = 35, ["IgA_MTY"] = 40,
            ["PCRULMTY"] = 60
        };

        for (int i = 0; i < ReagentCodes.Length; i++)
        {
            var code = ReagentCodes[i];
            var baseStock = stockBase.GetValueOrDefault(code, 50);
            Records.Add(new ReagentGridRecord
            {
                ReagentCode = code,
                ProductId = 1000 + i,
                Stock = baseStock + random.Next(-5, 5),
                Pacientes = 0,
                Repeticiones = 0,
                Control = 0,
                Calibracion = 0,
                Cancelacion = 0,
                MotivoCancelacion = "",
                Validacion = 0,
                SinIdentificar = 0,
                QueProveedor = true,
                Activo = 1,
                CalcAuto = 1
            });
        }
    }

    private List<string> ValidateAndSave()
    {
        var errors = new List<string>();
        var prefix = "ctl00$ContentMasterPage$grdConsumo$ctl";

        for (int i = 0; i < ReagentCodes.Length; i++)
        {
            var rowIndex = (i + 2).ToString("D2");
            var code = ReagentCodes[i];

            // Check if any values were submitted for this row
            var pacientesKey = $"{prefix}{rowIndex}$txtPacientes";
            var repeticionesKey = $"{prefix}{rowIndex}$txtRepeticiones";
            var controlKey = $"{prefix}{rowIndex}$txtControlCapMGrd";
            var calibracionKey = $"{prefix}{rowIndex}$txtCalibracionCapMGrd";
            var cancelacionKey = $"{prefix}{rowIndex}$txtCancelacionCapMGrd";

            if (Request.Form.ContainsKey(pacientesKey))
            {
                if (!int.TryParse(Request.Form[pacientesKey], out var pacientes) || pacientes < 0)
                    errors.Add($"Pacientes invalido para {code}: {Request.Form[pacientesKey]}");
            }

            if (Request.Form.ContainsKey(repeticionesKey))
            {
                if (!int.TryParse(Request.Form[repeticionesKey], out var repeticiones) || repeticiones < 0)
                    errors.Add($"Repeticiones invalido para {code}: {Request.Form[repeticionesKey]}");
            }

            if (Request.Form.ContainsKey(controlKey))
            {
                if (!int.TryParse(Request.Form[controlKey], out var control) || control < 0)
                    errors.Add($"Control invalido para {code}: {Request.Form[controlKey]}");
            }

            if (Request.Form.ContainsKey(calibracionKey))
            {
                if (!int.TryParse(Request.Form[calibracionKey], out var calibracion) || calibracion < 0)
                    errors.Add($"Calibracion invalido para {code}: {Request.Form[calibracionKey]}");
            }

            if (Request.Form.ContainsKey(cancelacionKey))
            {
                if (!int.TryParse(Request.Form[cancelacionKey], out var cancelacion) || cancelacion < 0)
                    errors.Add($"Cancelacion invalido para {code}: {Request.Form[cancelacionKey]}");
            }
        }

        return errors;
    }
}
