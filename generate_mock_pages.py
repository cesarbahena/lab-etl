#!/usr/bin/env python3
"""
Generate 25 paginated HTML mock pages for LIMS testing
"""
from datetime import datetime, timedelta
import random
import os

# Sample data pools
clients = [101, 102, 103, 104, 105]
sucursales = ["Lab West", "Lab East", "Lab North", "Lab South", "Branch A", "Branch B", "Branch C"]
maquiladores = ["Quest Labs", "LabCorp", "Maq X", "Maq Y", "Maq Z"]
labels = ["Blood Test", "Urine Test", "CBC", "Chemistry Panel", "Lipid Panel", "Glucose", "Hemogram"]
priorities = ["Normal", "Urgent", "Stat", "Routine"]

def generate_sample_row(index, folio_base, date_base):
    """Generate a single sample row"""
    row_num = str(index).zfill(2)

    # Generate dates
    fecha_grd = date_base - timedelta(hours=random.randint(0, 2))
    fecha_recep = fecha_grd + timedelta(minutes=random.randint(30, 90))
    fec_cap_res = fecha_recep + timedelta(hours=random.randint(2, 8))
    fec_libera = fec_cap_res + timedelta(hours=random.randint(1, 24))
    fec_nac = datetime(random.randint(1950, 2000), random.randint(1, 12), random.randint(1, 28))

    # Generate IDs
    folio = folio_base + index
    cliente = random.choice(clients)
    paciente = random.randint(100, 999)
    est_per = random.randint(100, 999)

    # Generate labels
    label1 = random.choice(labels)
    label3 = random.choice(priorities)
    suc_proc = random.choice(sucursales)
    maquilador = random.choice(maquiladores)

    # Format dates
    def fmt_datetime(dt):
        return dt.strftime("%d/%m/%Y %I:%M:%S %p")

    def fmt_date(dt):
        return dt.strftime("%d/%m/%Y")

    return f'''            <!-- Data Row {index-1} -->
            <tr>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblFechaGrd">{fmt_datetime(fecha_grd)}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblFechaRecep">{fmt_datetime(fecha_recep)}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblFolioGrd">{folio}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblClienteGrd">{cliente}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblPacienteGrd">{paciente}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblEstPerGrd">{est_per}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_Label1">{label1}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblFecCapRes">{fmt_datetime(fec_cap_res)}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblFecLibera">{fmt_datetime(fec_libera)}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblSucProc">{suc_proc}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblMaquilador">{maquilador}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_Label3">{label3}</span></td>
                <td><span id="ctl00_ContentMasterPage_grdConsultaOT_ctl{row_num}_lblFecNac">{fmt_date(fec_nac)}</span></td>
            </tr>'''

def generate_pagination(current_page, total_pages=25):
    """
    Generate ASP.NET GridView pagination - blocks of 10 pages

    Structure matching original muestras.py logic:
    - Block 1: [1] [2] ... [10] [11]
      - Current page: NO <a> tag
      - Other pages in block: HAS <a> tag
      - Boundary marker (11): HAS <a> to advance to next block
    - Block 2+: [<] [11] [12] ... [20] [21]
      - td[1]: Back link to previous block (for skim() line 243)
      - Current page: NO <a> tag
      - Other pages in block: HAS <a> tag
      - Boundary marker (21): HAS <a> to advance to next block
    """
    pagination_items = []

    # Determine current block (pages are grouped in blocks of 10)
    block_start = ((current_page - 1) // 10) * 10 + 1
    block_end = min(block_start + 9, total_pages)

    # Add back navigation link for blocks 2+ (td[1]/a from line 243)
    if block_start > 1:
        # td[1]: Link back to last page of previous block
        prev_block_last = block_start - 1
        pagination_items.append(f'<td><a href="consulta_page_{prev_block_last}.html">...</a></td>')

    # Generate pages in current block
    for p in range(block_start, block_end + 1):
        if p == current_page:
            # Current page: NO <a> tag (detected by exception in position())
            pagination_items.append(f'<td>{p}</td>')
        else:
            # Other pages in block: HAS <a> tag
            pagination_items.append(f'<td><a href="consulta_page_{p}.html">{p}</a></td>')

    # Add boundary marker if more pages exist beyond current block
    if block_end < total_pages:
        # Boundary marker (first page of next block) - clickable to advance blocks
        pagination_items.append(f'<td><a href="consulta_page_{block_end + 1}.html">...</a></td>')

    return '\n                                '.join(pagination_items)

def generate_page_html(page_num, cliente=101):
    """Generate complete HTML page"""
    # Base date: start from recent and go back in time
    base_date = datetime(2023, 3, 20) - timedelta(days=(page_num - 1) * 2)
    folio_base = 100000 + ((page_num - 1) * 10)

    # Generate 10 rows per page
    rows = []
    for i in range(2, 12):  # Rows 2-11
        row_date = base_date - timedelta(hours=(i-2) * 3)
        rows.append(generate_sample_row(i, folio_base, row_date))

    pagination = generate_pagination(page_num)

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Mock Consulta Orden Trabajo - Page {page_num}</title>
</head>
<body>
    <h1>Mock Consulta Orden Trabajo - Page {page_num}/25</h1>
    <div>
        <label for="ctl00_ContentMasterPage_txtcliente">Cliente:</label>
        <input type="text" id="ctl00_ContentMasterPage_txtcliente" name="cliente" value="{cliente}">
        <input type="submit" id="ctl00_ContentMasterPage_btnBuscar" value="Buscar">
    </div>
    <hr>
    <table id="ctl00_ContentMasterPage_grdConsultaOT">
        <tbody>
            <!-- Header Row -->
            <tr>
                <th>Fecha</th>
                <th>Recep</th>
                <th>Folio</th>
                <th>Cliente</th>
                <th>Paciente</th>
                <th>Est/Per</th>
                <th>Label1</th>
                <th>FecCapRes</th>
                <th>FecLibera</th>
                <th>SucProc</th>
                <th>Maquilador</th>
                <th>Label3</th>
                <th>FecNac</th>
            </tr>
{chr(10).join(rows)}
            <!-- Pagination Row (index 12 in scraper) -->
            <tr class="pagination-row">
                <td colspan="13">
                    <table>
                        <tbody>
                            <tr>
                                {pagination}
                            </tr>
                        </tbody>
                    </table>
                </td>
            </tr>
        </tbody>
    </table>
    <span id="ctl00_ContentMasterPage_lblUsuarioCaptura">{cliente}</span>
</body>
</html>
'''
    return html

def main():
    """Generate all 25 pages"""
    print("Generating 25 paginated HTML mock pages...")
    for page in range(1, 26):
        html = generate_page_html(page)
        filename = f"consulta_page_{page}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  Created: {filename}")

    # Update consulta.html to point to first page
    html = generate_page_html(1)
    with open("consulta.html", 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Updated: consulta.html (page 1)")

    print(f"\nGenerated 25 pages with 250 total samples (10 per page)")
    print(f"Date range: 2023-03-20 going back ~50 days")
    print(f"Folio range: 100002-100251")

if __name__ == "__main__":
    main()
