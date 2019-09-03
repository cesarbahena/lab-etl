using System;
using System.Collections.Generic;

namespace QuimiOSWebForms
{
    public sealed class InventorySnapshot
    {
        public long Version { get; set; }
        public Dictionary<string, decimal> Stock { get; set; }
    }

    public sealed class MockInventoryStore
    {
        public static readonly string[] ReagentCodes = {
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

        private readonly object _gate = new object();
        private Dictionary<string, decimal> _stock;
        private long _version;

        public MockInventoryStore()
        {
            var random = new Random(42);
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
            _stock = new Dictionary<string, decimal>(StringComparer.Ordinal);
            foreach (var code in ReagentCodes)
            {
                decimal baseStock;
                if (!stockBase.TryGetValue(code, out baseStock))
                    baseStock = 50;
                _stock.Add(code, baseStock + random.Next(-5, 5));
            }
        }

        public InventorySnapshot Read()
        {
            lock (_gate)
            {
                return new InventorySnapshot
                {
                    Version = _version,
                    Stock = new Dictionary<string, decimal>(_stock, StringComparer.Ordinal)
                };
            }
        }

        public string Apply(long expectedVersion, Dictionary<string, decimal> consumption)
        {
            lock (_gate)
            {
                if (expectedVersion != _version)
                    return "El inventario cambió. Actualice la consulta antes de guardar.";

                var next = new Dictionary<string, decimal>(_stock, StringComparer.Ordinal);
                foreach (var item in consumption)
                {
                    decimal current;
                    if (!next.TryGetValue(item.Key, out current))
                        return "Reactivo desconocido: " + item.Key;
                    decimal remaining;
                    try
                    {
                        remaining = checked(current - item.Value);
                    }
                    catch (OverflowException)
                    {
                        return "Cantidad fuera de rango para " + item.Key;
                    }
                    if (remaining < 0)
                        return "Existencia insuficiente para " + item.Key;
                    next[item.Key] = remaining;
                }

                _stock = next;
                if (consumption.Count > 0)
                    _version++;
                return null;
            }
        }
    }
}
