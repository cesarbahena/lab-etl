from selenium import webdriver
from selenium.webdriver.support.ui import Select
from time import sleep
from datetime import datetime
from datetime import timedelta
import pandas as pd
import shutil


dtypes = {
    '_lblFechaGrd': 'datetime64[ns]',
    '_lblFechaRecep': 'datetime64[ns]',
    '_lblFolioGrd': 'uint32',
    '_lblClienteGrd': 'uint16',
    '_lblPacienteGrd': 'uint16',
    '_lblEstPerGrd': 'uint16',
    '_Label1': 'category',
    '_lblFecCapRes': 'datetime64[ns]',
    '_lblFecLibera': 'datetime64[ns]',
    '_lblSucProc': 'category',
    '_lblMaquilador': 'category',
    '_Label3': 'category',
    '_lblFecNac': 'datetime64[ns]',
}
cols = list(dtypes.keys())
date_cols = ['_lblFechaGrd', '_lblFechaRecep',
             '_lblFecCapRes', '_lblFecLibera']
non_date_dtypes = {
    '_lblFolioGrd': 'uint32',
    '_lblClienteGrd': 'uint16',
    '_lblPacienteGrd': 'uint16',
    '_lblEstPerGrd': 'uint16',
    '_Label1': 'category',
    '_lblSucProc': 'category',
    '_lblMaquilador': 'category',
    '_Label3': 'category',
}
parse_cols = [0, 1, 7, 8, 12]


class Scraper:
    registry = []
    start = datetime(datetime.today().year, datetime.today(
    ).month, datetime.today().day, 23, 59, 59)
    end = datetime(2021, 1, 15)
    n = 500
    verbose = 2
    reg = False
    s = 2
    skip = False
    df = pd.DataFrame({col: [] for col in cols})
    file = 'Muestras.csv'
    stop = []

    def __init__(self, client):
        self.client = client
        self.dict = {col: [] for col in cols}
        self.fails = 0
        self.page = 1

    @classmethod
    def load(cls, file=None):
        '''
        Hace una dataframe de la información almacenada en csv paa poder trabajar con él.
        '''
        # Asigna la ruta del archivo en tiempo de ejecución y no de definición
        if file is None:
            file = 'Muestras.csv'
        cls.file = file
        # Genera una copia de respaldo
        backup(file)
        # Almacena el dataframe como atributo de clase para que todas las instancias de clientes puedan acceder a él
        info('load', cls.file)
        cls.df = pd.read_csv(file, dtype=non_date_dtypes,
                             parse_dates=parse_cols, dayfirst=True)

    def login(self):
        '''
        Revisa si hay una sesión de QUIMIOS-W abierta; si no, inicia sesión.
        '''
        try:
            Scraper.quimios.find_element_by_xpath(
                '//*[@id="aspnetForm"]/div[3]/div[1]/div/div/div/div[1]/span')
        except Exception:
            info('login')
            Scraper.quimios = webdriver.Chrome('chromedriver')
            Scraper.quimios.get('http://172.16.0.117/')
            Scraper.quimios.find_element_by_id(
                'Login1_UserName').send_keys('cbahena')
            Scraper.quimios.find_element_by_id(
                'Login1_Password').send_keys('alpe58')
            Scraper.quimios.find_element_by_id('Login1_LoginButton').click()
            sleep(Scraper.s*2)

    def reset(self):
        '''
        Busca el número de cliente en consulta de órdenes de trabajo.
        '''
        try:
            if int(Scraper.quimios.find_element_by_xpath('//*[@id="ctl00_ContentMasterPage_lblUsuarioCaptura"]').text) != self.client:
                info('reset', self.client)
                Scraper.quimios.get(
                    'http://172.16.0.117/FasePreAnalitica/ConsultaOrdenTrabajo.aspx')
                Scraper.quimios.find_element_by_id(
                    'ctl00_ContentMasterPage_txtcliente').send_keys(self.client)
                Scraper.quimios.find_element_by_id(
                    'ctl00_ContentMasterPage_btnBuscar').click()
                sleep(Scraper.s*2)
        except Exception:
            info('reset', self.client)
            Scraper.quimios.get(
                'http://172.16.0.117/FasePreAnalitica/ConsultaOrdenTrabajo.aspx')
            Scraper.quimios.find_element_by_id(
                'ctl00_ContentMasterPage_txtcliente').send_keys(self.client)
            Scraper.quimios.find_element_by_id(
                'ctl00_ContentMasterPage_btnBuscar').click()
            sleep(Scraper.s*2)

    def get(self, row, col):
        '''
        Realiza web scrapping para conseguir los datos de la fila y columna especificada.
        '''
        return Scraper.quimios.find_element_by_id(f'ctl00_ContentMasterPage_grdConsultaOT_ctl{str(row).zfill(2)}{col}').text

    def parse(self, row, col):
        '''
        Realiza web scrapping para conseguir la fecha de la fila y columna especificada.
        '''
        try:
            return datetime.strptime(f'{self.get(row, col)[:-3]}{self.get(row, col)[-2]}', '%d/%m/%Y %I:%M:%S %p')
        except Exception:
            return datetime(2099, 12, 31)

    def birth(self, row):
        '''
        Realiza web scrapping para conseguir la fecha de nacimiento de la fila especificada.
        '''
        return datetime.strptime(self.get(row, '_lblFecNac'), '%d/%m/%Y')

    def scan(self):
        '''
        Escanea la página para buscar muestras recibidas entre las fechas especificadas y almacenar sus datos relevantes en un diccionario para despues convertirlos a un DataFrame.
        '''
        # Revisar todas las filas
        for row in range(2, 12):
            # Revisar si está entre las fechas especificadas
            if Scraper.start > self.parse(row, '_lblFechaRecep') > Scraper.end:
                # Revisar todas las columnas
                info('row', row)
                for col in cols:
                    # Revisar si es columna de fecha
                    if col in date_cols:
                        # Extraer fecha
                        try:
                            self.dict[col].append(self.parse(row, col))
                        # Generar valor nulo si falla
                        except Exception:
                            self.dict[col].append(pd.NaT)
                    elif col != '_lblFecNac':
                        # Extraer datos
                        try:
                            self.dict[col].append(self.get(row, col))
                        # Generar 0 si falla
                        except Exception:
                            self.dict[col].append(0)
                # Extraer fecha de nacimiento
                try:
                    self.dict['_lblFecNac'].append(self.birth(row))
                # Generar valor nulo si falla
                except Exception:
                    self.dict['_lblFecNac'].append(pd.NaT)
            else:
                self.fails += 1

    def position(self):
        '''
        Determina la posición actual entre los números de pagina.
        '''
        # Revisar todos los números de página
        for page in range(1, 13):
            try:
                Scraper.quimios.find_element_by_xpath(
                    f'//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[{page}]/a')
            # Cuando encuentre la primera excepción, significa que no encuentra ese element porque es la página actual
            except Exception:
                self.page = page
                break

    def next(self):
        '''
        Hace clic en la página siguiente.
        '''
        Scraper.quimios.find_element_by_xpath(
            f'//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[{self.page + 1}]/a').click()
        sleep(Scraper.s)

    def search(self):
        '''
        Inicia la búsqueda de las muestras recibidas tomando en cuenta los parámetros por default o los especificados en la función options().
        '''
        # Resetea el contador de intentos fallidos de extraer las muestras recibidas entre las fechas especificadas
        self.fails = 0
        # Loop para continuar buscando hasta que se supere el número de intentos fallidos permitido (n)
        while self.fails < Scraper.n:
            self.position()
            self.scan()
            try:
                self.next()
                info('next', self.page + 1)
            # Si no hay página siguiente, detener el loop
            except Exception:
                info('missing', self.page + 1)
                Scraper.stop.append(f'{self.client}, ')
                break

    def skim(self):
        '''
        Busca rápido entre las páginas si hay muestras entre las fechas especificadas.
        '''
        # Bloque de páginas actual
        block = 0
        # Loop para verificar si la fecha de recepción de la muestra en la última fila está a menos de 1 mes de la fecha especificada
        while self.parse(11, '_lblFechaRecep') > Scraper.start + timedelta(30):
            # Hacer una lista de las páginas faltantes
            missing = []
            for page in range(1, 14):
                try:
                    Scraper.quimios.find_element_by_xpath(
                        f'//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[{page}]/a')
                # Cuando encuentre la primera excepción, significa que no encuentra ese elemento porque es la página actual
                except Exception:
                    missing.append(page)
            # Determinar la última página, la cuál es la segunda ocurrencia de la excepción (la primera es la página actual)
            last = missing[1] - 1
            # Dar clic en la última página para avanzar rápido
            try:
                Scraper.quimios.find_element_by_xpath(
                    f'//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[{last}]/a').click()
                block += 10
                info('last', block)
            except Exception:
                info('missing last', block + 10)
                break
            sleep(Scraper.s)

        # Después de encontrar una fecha con menos de 1 mes de diferencia, regresar al bloque de páginas anterior y luego ir a la primera página del bloque
        try:
            Scraper.quimios.find_element_by_xpath(
                f'//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[1]/a').click()
            sleep(Scraper.s)
            info('prev')
        except Exception:
            info('no prev')
        try:
            Scraper.quimios.find_element_by_xpath(
                f'//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[2]/a').click()
            sleep(Scraper.s)
            info('first', block - 10)
        except Exception:
            info('no first')

        # Busqueda página por página hasta encontrar la fecha especificada
        while self.parse(11, '_lblFechaRecep') > Scraper.start:
            self.position()
            try:
                self.next()
                info('next', self.page)
            # Si no hay página siguiente, detener el loop
            except Exception:
                break

        # Determinar posición y regresar una página
        self.position()
        try:
            Scraper.quimios.find_element_by_xpath(
                f'//*[@id="ctl00_ContentMasterPage_grdConsultaOT"]/tbody/tr[12]/td/table/tbody/tr/td[{self.page - 1}]/a').click()
            sleep(Scraper.s)
            info('prev')
        except Exception:
            info('no prev')

    def save(self, file=None):
        '''
        Guarda la información en un archivo csv.
        '''
        # Asigna la ruta del archivo en tiempo de ejecución y no de definición
        if file is None:
            file = 'Muestras.csv'
        Scraper.file = file
        info('save', Scraper.file)
        Scraper.df.to_csv(file, index=False)


def main():
    '''
    Ejecuta la función principal del script: extraer las muestras recibidas de todos los clientes (o los clientes especificados) entre las fechas especificadas.
    '''
    # Carga el archivo csv con la información almacenada anteriormente
    Scraper.load()
    # Loop para pedir una lista (válida) de los clientes a buscar
    while True:
        input_ = input(
            'Clientes (separados con comas) o enter para buscar todos: ')
        # Si se presiona enter con una string vacía, cargar la lista de todos los clientes (csv) y convertirla a una serie de pandas
        if input_ == '':
            clients = pd.read_csv('Clientes.csv', squeeze=True)
            break
        # Si se teclea algo, verificar que sean números válidos
        else:
            try:
                clients = [int(cliente) for cliente in input_.split(',')]
                break
            except Exception:
                print('Entrada inválida')

    # Sí la lista es de un solo cliente, preguntar si se desea avanzar rápido entre las páginas para llegar a la fecha deseada
    if len(clients) == 1:
        Scraper.skip = False
        # Loop para verificar respuesta válida
        while True:
            input_ = input('¿Saltar páginas? 0: No  1: Sí')
            if input_ == '1':
                Scraper.skip = True
                break
            elif input_ == '0':
                break

    # Preguntar si se desea cambiar ajustes
    options()

    # Loop para buscar todos los clientes
    for client in clients:
        # Crear instancia del cliente
        c = Scraper(client)
        # Iniciar sesión si es necesario
        c.login()
        # Buscar el número de cliente en Consulta de órdenes de trabajo si es necesario
        c.reset()
        # Saltar rápido entre las páginas si se seleccionó la opción
        if Scraper.skip:
            c.skim()
        # Extraer las muestras recibidas del cliente y almacenarlas en un diccionario
        c.search()
        # Crear dataframe del diccionario y concatenarlo con el dataframe de clase que contiene todas las muestras
        Scraper.df = pd.concat(
            [Scraper.df, pd.DataFrame(c.dict).astype(dtype=dtypes)])
        # Guarda la información antes de continuar con otro cliente
        c.save()


def options():
    '''
    Inicia la interfaz para ajustar las opciones de búsqueda.
    '''
    # Resetear los ajustes por default
    Scraper.start = datetime(datetime.today().year, datetime.today(
    ).month, datetime.today().day, 23, 59, 59)
    Scraper.n = 500
    Scraper.verbose = 2
    Scraper.reg = False
    Scraper.s = 2
    Scraper.stop = []

    # Loop para pedir una fecha válida para el límite inferior de extracción de datos
    while True:
        input_ = input('¿Hasta que fecha extraer los datos?: ')
        try:
            end = datetime(int('20' + input_.replace('/', '-').split('-')[2][-2:]), int(input_.replace(
                '/', '-').split('-')[1]), int(input_.replace('/', '-').split('-')[0]), 23, 59, 59)
            break
        except Exception:
            print('Entrada inválida')
    Scraper.end = end

    # Loop para la interfaz de ajustes
    while True:
        try:
            # Pedir al usuario que seleccione una opción (y seguir preguntando si no es una opción válida)
            settings = int(input('0: Continuar sin modificar ajustes\n1: No extraer datos hasta la fecha de hoy\n2: Numero de muestras fuera de las fechas especificadas antes de detener la búsqueda\n3: Detalle a mostrar de las acciones en tiempo real\n4: Activar o desactivar el registro de acciones\n5: Tiempo de espera en caso de mala conexión'))

            # Cada if revisa si la opción seleccionada es una de las opciones válidas
            if settings == 1:
                # Cada while True verifica que la variable a modificar sea válida
                while True:
                    input_ = input('¿Hasta que fecha extraer los datos?: ')
                    try:
                        start = datetime(int('20' + input_.replace('/', '-').split('-')[2][-2:]), int(
                            input_.replace('/', '-').split('-')[1]), int(input_.replace('/', '-').split('-')[0]))
                        break
                    except Exception:
                        print('Entrada inválida')
                Scraper.start = start
            if settings == 2:
                while True:
                    try:
                        input_ = int(input(
                            'Numero de muestras fuera de las fechas especificadas antes de detener la búsqueda: '))
                        break
                    except Exception:
                        print('Entrada inválida')
                Scraper.n = input_
            if settings == 3:
                while True:
                    try:
                        input_ = int(input(
                            '0: No mostrar acciones en tiempo real\n1: Mostrar acciones importantes en tiempo real\n2: Mostrar todas las acciones en tiempo real: '))
                        if input_ in (0, 1, 2):
                            break
                    except Exception:
                        print('Entrada inválida')
                Scraper.verbose = input_
            if settings == 4:
                while True:
                    try:
                        input_ = int(
                            input('0: Desactivar registro de acciones\n1: Activar registro de acciones'))
                        if input_ in (0, 1):
                            break
                    except Exception:
                        print('Entrada inválida')
                Scraper.reg = input_
            if settings == 5:
                while True:
                    try:
                        input_ = int(
                            input('Tiempo de espera (segundos) en caso de mala conexión: '))
                        break
                    except Exception:
                        print('Entrada inválida')
                Scraper.s = input_

            # Si se selecciona 0, terminar el loop y continuar
            if settings == 0:
                break
            # Se se selecciona una entrada inválida, volver a preguntar
        except Exception:
            print('Entrada inválida')


def backup(file=None):
    if file is None:
        file = 'Muestras.csv'
    shutil.copyfile(
        file, file[:-4]+' '+str(datetime.now()).replace(':', "'")[:-10]+'.csv')


def info(step, variable='x'):
    # Filtro en caso de que no se requiera executar la función request() para obtener información
    if Scraper.verbose > 0 or Scraper.reg:
        request(step, variable)


def request(step, variable):
    # Definir el diccionario de comentarios
    commentaries = {
        'load': [f'Cargando {variable}', f'Cargando {variable}'],
        'login': ['Iniciando sesión', 'Iniciando sesión'],
        'reset': [f'Buscando cliente {variable}...', f'Buscando cliente {variable}...'],
        'scan': [f'Buscando en la página {variable}', f'Buscando en la página {variable}'],
        'row': [f'Extrayendo fila {variable}'],
        'next': [f'Siguiente página {variable}', f'Siguiente página {variable}'],
        'missing': [f'No hay página {variable}', f'No hay página {variable}'],
        'last': [f'Saltando a las páginas {variable}s', f'Saltando a las páginas {variable}s'],
        'last missing': [f'No hay páginas {variable}s', f'No hay páginas {variable}s'],
        'prev': [f'Regresando a la página anterior', 'Regresando a la página anterior'],
        'no prev': [f'No hay página anterior', 'No hay página anterior'],
        'first': [f'Saltando al inicio de las páginas {variable}s', f'Saltando al inicio de las páginas {variable}s'],
        'no first': ['No se puede acceder al inicio del bloque de páginas', 'No se puede acceder al inicio del bloque de páginas'],
        'save': [f'Guardando en {variable}', f'Guardando en {variable}'],
    }
    # Verificar si está activado el registro de acciones
    if Scraper.reg:
        Scraper.registry.append((datetime.now(), commentaries[step][0]))
    # Verificar el nivel de información en tiempo real que se requiere
    if Scraper.verbose == 1:
        # Si es nivel 1, intentar acceder al índice 1 que contiene solo la información necesaria para el nivel 1
        try:
            print(commentaries[step][1])
        except Exception:
            pass
    elif Scraper.verbose == 2:
        # Si es nivel 2, acceder al índice 0 que contiene toda la información
        print(commentaries[step][0])


if __name__ == '__main__':
    # Correr una vez la función principal del script
    main()
    # Ciclo para volver a correr función principal del script hasta que se seleccione salir
    while True:
        input_ = input('¿Seguir buscando?: 0: No   1: Sí')
        if input_ == '0':
            break
        if input_ == '1':
            main()
        else:
            print('Entrada inválida')

    print(
        f'Revisar si se extrajeron todas las muestras deseadas de los clientes {"".join(Scraper.stop)}'[:-2])
