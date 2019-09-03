using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using System.Text;

namespace QuimiOSWebForms.Pages
{

public class ReagentGridRecord
{
    public string ReagentCode { get; set; } = "";
    public int ProductId { get; set; }
    public decimal Stock { get; set; }
    public decimal Pacientes { get; set; }
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
    private readonly MockInventoryStore _inventory;
    private long _renderedVersion;

    public ConsumoReacLabMasivoModel(MockInventoryStore inventory)
    {
        _inventory = inventory;
    }

    public string ViewState { get; set; } = "";
    public string ViewStateGenerator { get; set; } = "";
    public string EventValidation { get; set; } = "";
    public string HfActivo { get; set; } = "0";
    public string HfCalcAuto { get; set; } = "1";
    public string FechaDesde { get; set; } = DateTime.Now.AddDays(-7).ToString("dd/MM/yyyy");
    public string FechaHasta { get; set; } = DateTime.Now.ToString("dd/MM/yyyy");
    public string LoggedInUser { get; set; } = "";
    public string ErrorMessage { get; set; }
    public string SuccessMessage { get; set; }
    public List<ReagentGridRecord> Records { get; set; } = new List<ReagentGridRecord>();

    public IActionResult OnGet()
    {
        if (!IsAuthenticated())
            return RedirectToPage("/Login");

        LoggedInUser = HttpContext.Session.GetString("User") ?? "demo_user";
        RenderGrid();
        return Page();
    }

    public IActionResult OnPost()
    {
        if (!IsAuthenticated())
            return RedirectToPage("/Login");

        LoggedInUser = HttpContext.Session.GetString("User") ?? "demo_user";
        if (!HasCurrentFormState())
        {
            ErrorMessage = "La consulta venció. Actualice el inventario antes de guardar.";
            RenderGrid();
            return Page();
        }

        // Handle search button
        if (Request.Form.ContainsKey("ctl00$ContentMasterPage$btnBuscarEstudio"))
        {
            RenderGrid();
            return Page();
        }

        // Handle save button
        if (Request.Form.ContainsKey("ctl00$ContentMasterPage$btnGuardaMasivo"))
        {
            Dictionary<string, decimal> consumption;
            var validationErrors = ValidateConsumption(out consumption);
            if (validationErrors.Count == 0)
            {
                long expectedVersion;
                if (!long.TryParse(HttpContext.Session.GetString("InventoryVersion"),
                                   NumberStyles.None, CultureInfo.InvariantCulture,
                                   out expectedVersion))
                    validationErrors.Add("La consulta venció. Actualice el inventario.");
                else
                {
                    var storeError = _inventory.Apply(expectedVersion, consumption);
                    if (storeError != null)
                        validationErrors.Add(storeError);
                }
            }
            if (validationErrors.Count > 0)
            {
                ErrorMessage = string.Join("; ", validationErrors);
                RenderGrid();
                return Page();
            }

            SuccessMessage = "Consumos guardados correctamente";
            RenderGrid();
            return Page();
        }

        RenderGrid();
        return Page();
    }

    private bool IsAuthenticated()
    {
        return HttpContext.Session.GetString("Authenticated") == "true";
    }

    private bool HasCurrentFormState()
    {
        var expected = HttpContext.Session.GetString("InventoryViewState");
        return expected != null && string.Equals(
            Request.Form["__VIEWSTATE"].ToString(), expected, StringComparison.Ordinal);
    }

    private void RenderGrid()
    {
        GenerateRecords();
        GenerateViewState();
    }

    private void GenerateViewState()
    {
        var timestamp = DateTime.UtcNow.Ticks.ToString();
        var stateData = $"Page=ConsumoReacLabMasivo|Timestamp={timestamp}|Session={HttpContext.Session.Id}|Version={_renderedVersion}";
        ViewState = Convert.ToBase64String(Encoding.UTF8.GetBytes(stateData));
        HttpContext.Session.SetString("InventoryViewState", ViewState);
        HttpContext.Session.SetString("InventoryVersion", _renderedVersion.ToString(CultureInfo.InvariantCulture));

        var vsgData = $"Generator={timestamp.GetHashCode() % 10000}";
        ViewStateGenerator = Convert.ToBase64String(Encoding.UTF8.GetBytes(vsgData)).Substring(0, 20);

        var allowedEvents = $"/Inventarios/ConsumoReacLabMasivo:btnBuscarEstudio|/Inventarios/ConsumoReacLabMasivo:btnGuardaMasivo|{timestamp}";
        EventValidation = Convert.ToBase64String(Encoding.UTF8.GetBytes(allowedEvents));
    }

    private void GenerateRecords()
    {
        var snapshot = _inventory.Read();
        _renderedVersion = snapshot.Version;
        Records.Clear();
        for (int i = 0; i < MockInventoryStore.ReagentCodes.Length; i++)
        {
            var code = MockInventoryStore.ReagentCodes[i];
            Records.Add(new ReagentGridRecord
            {
                ReagentCode = code,
                ProductId = 1000 + i,
                Stock = snapshot.Stock[code],
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

    private List<string> ValidateConsumption(out Dictionary<string, decimal> consumption)
    {
        var errors = new List<string>();
        consumption = new Dictionary<string, decimal>(StringComparer.Ordinal);
        var prefix = "ctl00$ContentMasterPage$grdConsumo$ctl";

        foreach (var key in Request.Form.Keys)
        {
            if (!key.StartsWith(prefix, StringComparison.Ordinal))
                continue;
            var suffix = key.Substring(prefix.Length);
            int row;
            if (suffix.Length < 3 || !int.TryParse(suffix.Substring(0, 2), out row) ||
                suffix[2] != '$' || row < 2 || row >= MockInventoryStore.ReagentCodes.Length + 2)
                errors.Add("Fila de reactivo desconocida: " + key);
        }

        for (int i = 0; i < MockInventoryStore.ReagentCodes.Length; i++)
        {
            var rowIndex = (i + 2).ToString("D2");
            var code = MockInventoryStore.ReagentCodes[i];
            var rowPrefix = prefix + rowIndex + "$";
            if (!Request.Form.Keys.Any(key => key.StartsWith(rowPrefix, StringComparison.Ordinal)))
                continue;

            var productKey = rowPrefix + "hfIDProducto";
            int productId;
            if (Request.Form[productKey].Count != 1 ||
                !int.TryParse(Request.Form[productKey], out productId) || productId != 1000 + i)
                errors.Add("Producto inválido para " + code);

            var px = ReadAmount(rowPrefix + "txtPacientes", code, true, errors);
            var rep = ReadAmount(rowPrefix + "txtRepeticiones", code, false, errors);
            var qc = ReadAmount(rowPrefix + "txtControlCapMGrd", code, false, errors);
            var cal = ReadAmount(rowPrefix + "txtCalibracionCapMGrd", code, false, errors);
            var canc = ReadAmount(rowPrefix + "txtCancelacionCapMGrd", code, false, errors);
            try
            {
                var total = checked(px + rep + qc + cal + canc);
                if (total != 0)
                    consumption.Add(code, total);
            }
            catch (OverflowException)
            {
                errors.Add("Cantidad fuera de rango para " + code);
            }
        }

        return errors;
    }

    private decimal ReadAmount(string key, string code, bool allowNegative, List<string> errors)
    {
        decimal amount;
        if (Request.Form[key].Count != 1 ||
            !decimal.TryParse(Request.Form[key],
                NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint,
                CultureInfo.InvariantCulture, out amount) ||
            (!allowNegative && amount < 0))
        {
            errors.Add("Cantidad inválida para " + code + ": " + key);
            return 0;
        }
        return amount;
    }
}
}
