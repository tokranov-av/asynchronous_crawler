
Программа асинхронной загрузки картинок из сайта https://xlcd.com

Алгоритм:
1. Определяются страницы с картинками и записываются их url адреса в очередь 1.
2. Из очереди 1 по очереди достаются адреса страниц с картинками, загружаются их html кода, после чего выполняется
парсинг для определения url адреса на саму картинку (на файл .jpeg или .png). Данный адрес записывается в очередь 2.
3. Из очереди 2 получаются по очереди url адреса на картинку и выполнятся их загрузка.
