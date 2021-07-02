'''
Написать функцию на Python 3.7+, которая получает на вход имя файла с отчетом в формате pdf или docx 
(желательно также поддерживать формат odt). Также на вход функции передается мета-описание информации, 
которая нужна для проверки в соответствии с выбранными критериями. Например, мета-описание может быть в 
виде словаря (множество пар ключ-значение) в питоне. На выходе функции - список замечаний, т.е. 
перечень критериев, которым отчет не удовлетворяет. Если список пустой, значит отчет в порядке

Написать скрипт, позволяющий применять данную функцию проверки отчетов к произвольному файлу. 
Имя файла с отчетом указывается как аргумент командной строки. Мета-описание считывается из 
второго файла в формате YAML, путь к которому также указывается в качестве аргумента командной строки
'''

import yaml
import sys
import os
import re
import pymorphy2
import difflib
import textract
# в данном случае для работы textract трбуется 2 дополнительные библиотеки: docx2txt и pdf2txt, 
# textract предоставляет общий интерфейс к данным библиотекам

''' Чтение словаря из yaml файла
    Входные данные: путь к YAML файлу
    Выходные данные: словарь с мета информацией для проверки
 '''
def meta_reader(meta_way):
    with open(meta_way, encoding = 'UTF-8') as f:
        return yaml.safe_load(f)

''' Нормализация текста (приведение символов в нижний регистр, 
    удаление лишних символов, установка каждлго слова в нормальную форму)
    Входные данные: строка текста
    Выходные данные: нормализованный список слов текста
'''
def normalize(text):
    text = text.lower()
    word_list = text.split()
    word_list = [re.sub(r'[^a-zа-я.\d]', u'', w) for w in word_list]
    word_list = [morph.parse(w)[0].normal_form for w in word_list]
    word_list = [w.replace('.', '') for w in word_list]
    word_list = [w for w in word_list if w]
    return word_list

''' Сравнительная функция поиска
    Используется для поиска текста по доли совпадения
    Входные параметры:  text - список строк, в котором осуществляется поиск
                        string - список строк, вхождение которых ищем
                        start_pos - стартовая позиция поиска (по умолчанию 0)
                        endpos - конечная позиция поиска (по умолчанию равна длине списка text)
    Выходные параметры: Позиция первого найденного вхождения  string в список text при заданной доли совпадения
                        или -1 если вхождение не обнаружено
'''
def comparison_search_function(text, string, start_pos = 0, endpos = 0, compliance = 1.0):
    if endpos == 0:
        endpos = len(text)
    searc_str = ''
    save_startpos = start_pos
    for w in string:
        searc_str += w
    save_pos = start_pos
    for i in range(len(string)):
        while start_pos < endpos - i:
            lst = text[start_pos : start_pos + i + 1]
            current_txt = ''.join(lst)
            #print('Сравнение: ', difflib.SequenceMatcher(None, searc_str, current_txt).ratio(), ' Требуется : ', compliance)
            if difflib.SequenceMatcher(None, searc_str, current_txt).ratio() >= compliance:
                #print('~~FIND -> ', searc_str, ' ::: ', current_txt, ' ::: current p: ' , difflib.SequenceMatcher(None, searc_str, current_txt).ratio(), ' need p : ', compliance)
                return start_pos
            start_pos += 1
        start_pos = save_pos
    return -1

''' Проверка текста из файла на наличие разделов и данных на титульном листе
    Входные данные: file_way - путь к файлу для проверки, 
                    meta - словарь с мета информацией для проверки
    Выходные данные: список замечаний (пустой - если замечаний нет), первый элемент списка - путь к проверенному файлу    
 '''
def checker(file_way, meta):
    if file_way.endswith('.pdf'):
        text = textract.process(file_way, method = 'pdftotext').decode('UTF-8', 'ignore')
    elif file_way.endswith('.docx') or file_way.endswith('.odt'):
        text = textract.process(file_way).decode('UTF-8', 'ignore')
    else:
        raise Exception("Invalid file format")
    print('Work with ', file_way, '...')
    normalize_text = normalize(text)
    check_list = [file_way]
        
    find_conclusion = -1 # Позиция раздела с выводом
    find_after_conclusion = -1 # Позиция раздела, идущего после вывода, если такой есть
    find_title_end_pos = len(normalize_text) # Позиция с началом первого найденного раздела (конец титульника)

    is_compared = False
    if  'Percentage of compliance' in meta and meta.get('Percentage of compliance') != None:
        is_compared = True

    # Ищем разделы работы по порядку
    start_pos = 0 # Стартовая позиция поиска первого раздела (начало документа)

    if 'Partition list' in meta and meta.get('Partition list') != None:
        for p in meta.get('Partition list'):
            if is_compared:
                position = comparison_search_function(normalize_text, normalize(p), start_pos, compliance = meta.get('Percentage of compliance'))
            else:
                position = comparison_search_function(normalize_text, normalize(p), start_pos)
            if position == -1:
                check_list.append('Not found partition: ' + p)
            else:
                if comparison_search_function(normalize(p), normalize('вывод')) != -1:
                    # Для большей точности определения положения вывода
                    find_conclusion = position + len(normalize(p))
                elif find_conclusion > -1:
                    # Для большей точности определения положения раздела после вывода
                    find_after_conclusion = position
                if position < find_title_end_pos:
                    find_title_end_pos = position

                start_pos = position

    # Некоторые студенты после вывода указывают дополнительные разделы не по заданию
    # Например, раздел "Приложение", который может содержать исходный код программы
    # Найдем его, если он не обязателен
    if find_conclusion > -1 and find_after_conclusion == -1: # Если мы нащли вывод
        find_after_conclusion = comparison_search_function(normalize_text, normalize('приложение'), start_pos = find_conclusion) 

    title_text = ''.join(normalize_text[0 : find_title_end_pos])
    #print(title_text)

    # Поиск на титульном листе (позиция от 0 до find_title_end_pos - позиция первого встреченного раздела)
    # Ищем название дисциплины:
    if ('Discipline name' in meta and meta.get('Discipline name') != None 
        and title_text.find(''.join(normalize(meta.get('Discipline name')))) == -1): #title_text.find(''.join(normalize(meta.get('Discipline name'))))
        check_list.append('Not found discipline name: ' + meta.get('Discipline name'))

    # Ищем название работы:
    if ('Job title' in meta and meta.get('Job title') != None 
        and title_text.find(''.join(normalize(meta.get('Job title')))) == -1):
        check_list.append('Not found job title: ' + meta.get('Job title'))

    # Ищем имя преподавателя:
    if ('Teacher name' in meta and meta.get('Teacher name') != None 
        and title_text.find(''.join(normalize(meta.get('Teacher name')))) == -1):
        check_list.append('Not found teacher name: ' + meta.get('Teacher name'))

    # Ищем должность преподавателя:
    if ('Teacher position' in meta and meta.get('Teacher position') != None 
    and title_text.find(''.join(normalize(meta.get('Teacher position')))) == -1):
        check_list.append('Not found teacher position: ' + meta.get('Teacher position'))
        
    # Ищем год выполнения работы:
    if ('Year' in meta and meta.get('Year') != None 
    and title_text.find(''.join(normalize(str(meta.get('Year'))))) == -1):
        check_list.append('Not found year: ' + str(meta.get('Year')))

    # Ищем обязательный текст
    if 'Text' in meta and meta.get('Text') != None:
        for t in meta.get('Text'):
            if is_compared:
                s_txt = comparison_search_function(normalize_text, normalize(t), compliance = meta.get('Percentage of compliance'))
            else:
                s_txt = comparison_search_function(normalize_text, normalize(t))
            if s_txt == -1:
                check_list.append('Not found text: ' + t)

    # Извлекаем выводы по следующей логике:
    # Если вывод найден (find_conclusion > -1), то проверяем существование раздела за выводом
    # (find_after_conclusion > -1):
    # Сущетвует - копируем в словарь значение пути к файлу и подстроку от начала вывода до начала следующего раздел
    # Не существует - копируем в словарь начение пути к файлу и подстроку от начала вывода и до конца строки
    if find_conclusion > -1:
        if find_after_conclusion > -1:
            conclusion_dict[file_way] = ''.join(normalize_text[find_conclusion:find_after_conclusion - 1])
        else:
            conclusion_dict[file_way] = ''.join(normalize_text[find_conclusion:len(normalize_text) - 1])
    if len(check_list) == 1: # Если в списке содержится только путь к файлу, чистим его
        check_list.clear()
    return check_list

''' "Проверка на плагиат" выводов, если совпадение 80% и более - вывод считается плагиатом
    Входные данные: список выводов
    Выходные данные: словарь пар Клдюч (путь к проверенному файлу) - Значение (список файлов, с которыми совпал вывод)
'''
def plagiat(conclusion_dict, identity = 1.0):
    conc_dict = {} # Помещаем в словарь плагиата значения: Ключ - путь к файлу, Значение - список путей файлов, где найдена схожесть
    for key in conclusion_dict:
        current_text = conclusion_dict.get(key)
        for pkey in conclusion_dict:
            percent = difflib.SequenceMatcher(None, current_text, conclusion_dict.get(pkey)).ratio()
            if pkey != key and percent >= identity:
                if not (key in conc_dict):
                    conc_dict[key] = []
                conc_dict[key].append(pkey + " Coincidence: " + '%.2f' % (percent * 100) + '%')
    return conc_dict

''' Точка входа '''
if __name__ == "__main__":
    try:
        if len(sys.argv) == 3:
            path = sys.argv[1]
            meta_way = sys.argv[2]
        else:
            raise Exception("No arguments found")
        meta = meta_reader(meta_way)
        #checker(path, meta)
    except Exception as e:
        print("Error: ", str(e))

    morph = pymorphy2.MorphAnalyzer() # Морфологический анализатор, используется для приведения слов в нормальную форму
    files = os.listdir(path)
    
    check_list = []
    conclusion_dict = {}

    for f in files:
        try:
            lst = checker(path + '/' + f, meta)
            if(len(lst) > 0):
                check_list.append(lst)
        except Exception as e:
            print("Check error: ", str(e))

    if 'Percentage of identity' in meta and meta.get('Percentage of identity') != None:
        conc_dict = plagiat(conclusion_dict, meta.get('Percentage of identity'))
    else:
        conc_dict = plagiat(conclusion_dict)

    print("\nList of remarks: ")
    # Выводим список замечаний
    for l in check_list:
        print(l)

    print("\nPlagiat:")
    # Выводим словарь плагиата
    for key in conc_dict:
        print('\n ---> file: ', key, ': ', conc_dict.get(key))
