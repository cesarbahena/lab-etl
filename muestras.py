from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from time import sleep
from datetime import datetime
import numpy as np
import pandas as pd
import shutil
import pdb
col_types = {'Fecha de captura': 'datetime64', 'Fecha de recepción': 'datetime64', 'Folio OT': 'uint32', 'Cliente': 'uint16', 'Progresivo': 'uint16', 'Apellido paterno': 'object', 'Apellido materno': 'object', 'Nombre': 'object', 'Código de estudio': 'uint16',
             'Nombre del estudio': 'category', 'Fecha de captura de resultado': 'datetime64', 'Fecha de liberación': 'datetime64', 'Sucursal de proceso': 'category', 'Maquilador': 'category', 'Nota de proceso': 'category', 'Fecha de nacimiento': 'datetime64', 'Fecha de actualización': 'datetime64'}
non_date_col_types = {'Folio OT': 'uint32', 'Cliente': 'uint16', 'Progresivo': 'uint16', 'Apellido paterno': 'object', 'Apellido materno': 'object', 'Nombre': 'object',
                      'Código de estudio': 'uint16', 'Nombre del estudio': 'category', 'Sucursal de proceso': 'category', 'Maquilador': 'category', 'Nota de proceso': 'category'}
col_names = list(col_types.keys())
date_cols = [0, 1, 10, 11, 15, 16]
chrome_options = Options()
chrome_options.headless = True
s = 2
verbose = True


def login():
    global quimios
    quimios = webdriver.Chrome('chromedriver')
    quimios.get('http://172.16.0.117/')
    quimios.find_element_by_id('Login1_UserName').send_keys('cbahena')
    quimios.find_element_by_id('Login1_Password').send_keys('alpe58')
    quimios.find_element_by_id('Login1_LoginButton').click()


def login_headless():
    global quimios
    quimios = webdriver.Chrome('chromedriver', options=chrome_options)
    quimios.get('http://172.16.0.117/')
    quimios.find_element_by_id('Login1_UserName').send_keys('cbahena')
    quimios.find_element_by_id('Login1_Password').send_keys('alpe58')
    quimios.find_element_by_id('Login1_LoginButton').click()


def get_client(client):
    quimios.get('http://172.16.0.117/FasePreAnalitica/ConsultaOrdenTrabajo.aspx')
    quimios.find_element_by_id(
        'ctl00_ContentMasterPage_txtcliente').send_keys(client)
    quimios.find_element_by_id('ctl00_ContentMasterPage_btnBuscar').click()
    sleep(s*2)


def get_col(row, col):
    return quimios.find_element_by_id('ctl00_ContentMasterPage_grdConsultaOT_ctl' + row + col).text


def get_date(row, col):
    try:
        return datetime.strptime(get_col(row, col)[:-3] + get_col(row, col)[-2], '%d/%m/%Y %I:%M:%S %p')
    except:
        return datetime(2099, 12, 31)


def get_nac(row, col):
    return datetime.strptime(get_col(row, col), '%d/%m/%Y')


def get_row(row):

    data = []

    try:
        data.append(get_date(row, '_lblFechaGrd'))
    except:
        data.append(pd.NaT)

    try:
        data.append(get_date(row, '_lblFechaRecep'))
    except:
        data.append(pd.NaT)

    try:
        data.append(int(get_col(row, '_lblFolioGrd')))
    except:
        data.append(0)

    try:
        data.append(int(get_col(row, '_lblClienteGrd')))
    except:
        data.append(0)

    try:
        data.append(int(get_col(row, '_lblPacienteGrd')))
    except:
        data.append(0)

    try:
        data.append(get_col(row, '_lblPaternoGrd'))
    except:
        data.append(pd.NA)

    try:
        data.append(get_col(row, '_lblApMaternoGrd'))
    except:
        data.append(pd.NA)

    try:
        data.append(get_col(row, '_lblNombreGrd'))
    except:
        data.append(pd.NA)

    try:
        data.append(int(get_col(row, '_lblEstPerGrd')))
    except:
        data.append(0)

    try:
        data.append(get_col(row, '_Label1'))
    except:
        data.append(pd.NA)

    try:
        data.append(get_date(row, '_lblFecCapRes'))
    except:
        data.append(pd.NaT)

    try:
        data.append(get_date(row, '_lblFecLibera'))
    except:
        data.append(pd.NaT)

    try:
        data.append(get_col(row, '_lblSucProc'))
    except:
        data.append(pd.NA)

    try:
        if get_col(row, '_lblMaquilador') != '':
            data.append(get_col(row, '_lblMaquilador'))
        else:
            data.append(pd.NA)
    except:
        data.append(pd.NA)

    try:
        data.append(get_col(row, '_Label3'))
    except:
        data.append(pd.NA)

    try:
        data.append(get_nac(row, '_lblFecNac'))
    except:
        data.append(pd.NaT)

    data.append(datetime.now())

    data = pd.DataFrame([data], columns=col_names)
    data = pd.DataFrame.astype(data, dtype=col_types)

    return data


def append_row(row, dataframe, day=datetime.today().day, month=datetime.today().month, year=datetime.today().year, n=10, to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year):
    global i
    if datetime(to_year, to_month, to_day, 23, 59, 59) > get_date(row, '_lblFechaRecep') > datetime(year, month, day):
        dataframe = pd.concat([dataframe, get_row(row)])
    else:
        i += 1
    return dataframe


def get_page(dataframe, day=datetime.today().day, month=datetime.today().month, year=datetime.today().year, n=10, to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year):
    for row in [str(num).zfill(2) for num in range(2, 12)]:
        if i < n:
            dataframe = append_row(row, dataframe, day,
                                   month, year, n, to_day, to_month, to_year)
    return dataframe


def next_page(page):
    quimios.find_element_by_xpath(
        '//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[' + str(page) + ']/a').click()
    sleep(s)


def skip_pages(to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year):
    current_page = 2
    next_page(11)
    while get_date('11', '_lblFechaRecep') > datetime(to_year, to_month, 28, 23, 59, 59):
        if verbose:
            print('next_page(fast loop)')
        next_page(12)
    next_page(1)
    next_page(2)
    while get_date('11', '_lblFechaRecep') > datetime(to_year, to_month, to_day, 23, 59, 59):
        for page in range(3, 13):
            if get_date('11', '_lblFechaRecep') > datetime(to_year, to_month, to_day, 23, 59, 59):
                if verbose:
                    print('next_page(slow loop)')
                next_page(page)
            else:
                current_page = page-1
                break
    if verbose:
        print(f'prev_page({current_page-1})')
    next_page(current_page-1)
    if verbose:
        print(f'current_page{current_page}')
    return current_page


def search_pages(dataframe, day=datetime.today().day, month=datetime.today().month, year=datetime.today().year, n=10, to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year):
    global i
    i = 0
    for page in range(2, 12):
        if i < n:
            if verbose:
                print(f'get_page({page-1})')
            dataframe = get_page(dataframe, day, month,
                                 year, n, to_day, to_month, to_year)
            try:
                if verbose:
                    print(f'next_page({page})')
                next_page(page)
            except:
                if verbose:
                    print(f'Breaking for loop because there is no page {page}')
                break
        else:
            if verbose:
                print('Breaking for loop')
            break
    if verbose:
        print(f'For loop completed')
    stop_sign = False
    while i < n:
        for page in range(3, 13):
            if i < n:
                if verbose:
                    print(f'get_page({page-1})')
                dataframe = get_page(dataframe, day, month,
                                     year, n, to_day, to_month, to_year)
                if verbose:
                    print(f'next_page({page})')
                try:
                    next_page(page)
                except:
                    if verbose:
                        print(
                            f'Breaking while loop because there is no page {page}')
                    stop_sign = True
                    break
            else:
                if verbose:
                    print('While loop completed')
                break
        if stop_sign:
            break
    return dataframe


def search_pages_after_skip(dataframe, day=datetime.today().day, month=datetime.today().month, year=datetime.today().year, n=10, to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year, current_page=2):
    global i
    i = 0
    for page in range(current_page, 13):
        if i < n:
            if verbose:
                print(f'get_page({page-1})')
            dataframe = get_page(dataframe, day, month,
                                 year, n, to_day, to_month, to_year)
            try:
                if verbose:
                    print(f'next_page({page})')
                next_page(page)
            except:
                if verbose:
                    print(f'Breaking for loop because there is no page {page}')
                break
        else:
            if verbose:
                print('Breaking for loop')
            break
    if verbose:
        print(f'For loop completed')
    stop_sign = False
    while i < n:
        for page in range(3, 13):
            if i < n:
                dataframe = get_page(dataframe, day, month,
                                     year, n, to_day, to_month, to_year)
                try:
                    if verbose:
                        print(f'next_page({page})')
                    next_page(page)
                except:
                    if verbose:
                        print(
                            f'Breaking while loop because there is no page {page}')
                    stop_sign = True
                    break
            else:
                if verbose:
                    print('While loop completed')
                break
        if stop_sign:
            break
    return dataframe


def search_pages_after_stop(dataframe, day=datetime.today().day, month=datetime.today().month, year=datetime.today().year, n=10, to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year):
    global i
    i = 0
    n = n*3
    current_page = 2
    last_page = 13
    try:
        if len(quimios.find_element_by_xpath('//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[' + str(2) + ']/a').text) == 1:
            last_page = 12
    except:
        try:
            if len(quimios.find_element_by_xpath('//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[' + str(3) + ']/a').text) == 1:
                last_page = 12
        except:
            pass
    for page in range(1, 12):
        try:
            quimios.find_element_by_xpath(
                '//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[' + str(page) + ']/a')
        except:
            current_page = page
            break
    next_page(current_page-2)
    for page in range(current_page-1, last_page):
        if i < n:
            if verbose:
                print(f'get_page({page-1})')
            dataframe = get_page(dataframe, day, month,
                                 year, n, to_day, to_month, to_year)
            try:
                if verbose:
                    print(f'next_page({page})')
                next_page(page)
            except:
                if verbose:
                    print(f'Breaking for loop because there is no page{page}')
                break
        else:
            if verbose:
                print('Breaking for loop')
            break
    if verbose:
        print(f'For loop completed')
    stop_sign = False
    while i < n:
        for page in range(3, 13):
            if i < n:
                if verbose:
                    print(f'get_page({page-1})')
                dataframe = get_page(dataframe, day, month,
                                     year, n, to_day, to_month, to_year)
                try:
                    if verbose:
                        print(f'next_page({page})')
                    next_page(page)
                except:
                    if verbose:
                        print(
                            f'Breaking while loop because there is no page {page}')
                    stop_sign = True
                    break
            else:
                if verbose:
                    print('While loop completed')
                break
        if stop_sign:
            break
    return dataframe


def append_recibidas(clients, dataframe, day=datetime.today().day, month=datetime.today().month, year=datetime.today().year, n=10, to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year):
    for client in clients:
        get_client(client)
        dataframe = search_pages(
            dataframe, day, month, year, n, to_day, to_month, to_year)
    return dataframe


def skip_then_append_recibidas(dataframe, day=datetime.today().day, month=datetime.today().month, year=datetime.today().year, n=10, to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year):
    if verbose:
        print('skip_pages()')
    current_page = skip_pages(to_day, to_month, to_year)
    if verbose:
        print('search_pages()')
    n = n*5
    dataframe = search_pages_after_skip(
        dataframe, day, month, year, n, to_day, to_month, to_year, current_page)
    return dataframe


def backup(file='Recibidas.csv'):
    shutil.copyfile(
        file, file[:-4]+' '+str(datetime.now()).replace(':', "'")[:-10]+'.csv')


def import_data(file='Recibidas.csv'):
    backup(file)
    dataframe = pd.read_csv(file, dtype=non_date_col_types,
                            parse_dates=date_cols, dayfirst=True).dropna(how='all')
    return dataframe


def save_data(dataframe, file):
    dataframe.to_csv(file, index=False)


def actualizar(file='Recibidas.csv', clients=pd.read_csv('Clientes.csv')['Clientes'], day=datetime.today().day, month=datetime.today().month, year=datetime.today().year, n=10, up_to_date=True, to_day=datetime.today().day, to_month=datetime.today().month, to_year=datetime.today().year, skip=False):
    global i
    global verbose
    if verbose:
        print('import_data()')
    dataframe = import_data(file)
    input_day = input('Día: ')
    if input_day != '':
        day = int(input_day)

    input_month = input('Mes: ')
    if input_month != '':
        month = int(input_month)

    input_year = input('Año: ')
    if input_year != '':
        year = int(input_year)

    input_up_to_date = input('¿A la fecha?: ')
    try:
        if input_up_to_date.upper()[0] == 'N':
            up_to_date = False
    except:
        pass

    if up_to_date:
        pass
    else:
        input_to_day = input('Día: ')
        if input_to_day != '':
            to_day = int(input_to_day)

        input_to_month = input('Mes: ')
        if input_to_month != '':
            to_month = int(input_to_month)

        input_to_year = input('Año: ')
        if input_to_year != '':
            to_year = int(input_to_year)

    input_clients = input('Clientes (separados con comas): ')
    if input_clients != '':
        clients = [cliente.strip() for cliente in input_clients.split(',')]
        if len(clients) == 1:
            input_skip = input('Saltar páginas: ')
            try:
                if input_skip.upper()[0] == 'S':
                    skip = True
            except:
                pass
            if skip:
                if verbose:
                    print('get_client()')
                get_client(clients[0])
                if verbose:
                    print('skip_then_append_recibidas()')
                dataframe = skip_then_append_recibidas(
                    dataframe, day, month, year, n, to_day, to_month, to_year)

            else:
                dataframe = append_recibidas(
                    clients, dataframe, day, month, year, n, to_day, to_month, to_year)
        else:
            dataframe = append_recibidas(
                clients, dataframe, day, month, year, n, to_day, to_month, to_year)
    else:
        dataframe = append_recibidas(
            clients, dataframe, day, month, year, n, to_day, to_month, to_year)
    if verbose:
        print('save_data()')
    save_data(dataframe, file)
    while True:
        continue_searching = input('¿Seguir buscando?: ')
        if continue_searching == '':
            break
        elif continue_searching[0].upper() == 'S':
            if verbose:
                print('Continuing the search')
            backup(file)
            input_day = input('Día: ')
            if input_day != '':
                day = int(input_day)

            input_month = input('Mes: ')
            if input_month != '':
                month = int(input_month)

            input_year = input('Año: ')
            if input_year != '':
                year = int(input_year)

            input_up_to_date = input('¿A la fecha?: ')
            try:
                if input_up_to_date.upper()[0] == 'N':
                    up_to_date = False
            except:
                pass

            if up_to_date:
                pass
            else:
                input_to_day = input('Día: ')
                if input_to_day != '':
                    to_day = int(input_to_day)

                input_to_month = input('Mes: ')
                if input_to_month != '':
                    to_month = int(input_to_month)

                input_to_year = input('Año: ')
                if input_to_year != '':
                    to_year = int(input_to_year)
            dataframe = search_pages_after_stop(
                dataframe, day, month, year, n, to_day, to_month, to_year)
            if verbose:
                print('save_data()')
            save_data(dataframe, file)
        else:
            break
    if verbose:
        print('Done.')


login()
actualizar(n=500)
