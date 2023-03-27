import asyncio
import logging
import os
from asyncio import Queue, Task
from concurrent.futures import ProcessPoolExecutor
from typing import List, Optional, Callable

import aiofiles
import aiohttp
from aiohttp import ClientSession, ClientResponse
from bs4 import BeautifulSoup

current_dir = os.path.dirname(os.path.abspath(__file__))
images_dir_path = os.path.join(current_dir, 'images')
logger = logging.getLogger()


async def make_request(
        url: str, session: ClientSession) -> Optional[ClientResponse]:
    """Корутина для запроса по указанному в url адресу"""
    response = await session.get(url)
    if response.ok:
        return response
    else:
        logger.error(f'{url} returned: {response.status}')


async def get_image_page(queue: Queue, session: ClientSession) -> None:
    """Корутина для получения страниц с изображениями после перенаправления"""
    url = 'https://c.xkcd.com/random/comic/'
    response = await make_request(url=url, session=session)
    if response is not None:
        await queue.put(response.url)


def parse_link(html: str) -> str:
    """Функция получения ссылки непосредственно на картинку"""
    soup = BeautifulSoup(html, 'lxml')
    image_link = f'https:{soup.select_one("div#comic>img").get("src")}'
    return image_link


async def get_image_url(pages_queue: Queue, image_urls_queue: Queue,
                        session: ClientSession) -> None:
    """
    Корутина получения ссылки на картинку из веб-страниц, адреса которых
     были получены get_image_page. После получения ссылки она помещается в
      другую очередь.
    """
    while True:
        url = await pages_queue.get()
        response = await make_request(url=url, session=session)

        if not response.ok:
            logger.error(f'{url} returned: {response.status}')
        else:
            html = await response.text()

            loop = asyncio.get_running_loop()
            with ProcessPoolExecutor() as pool:
                image_link = await loop.run_in_executor(
                    pool, parse_link, html
                )
            await image_urls_queue.put(image_link)

        pages_queue.task_done()


async def download_image(queue: Queue, session: ClientSession) -> None:
    """Корутина загрузки изображения"""
    while True:
        url = await queue.get()
        response = await make_request(url=url, session=session)
        if not response.ok:
            logger.error(f'{url} returned: {response.status}')
        else:
            filename = url.split('/')[-1]
            image_file_path = os.path.join(images_dir_path, filename)
            async with aiofiles.open(image_file_path, 'wb') as file:
                async for chunk in response.content.iter_chunked(1024):
                    await file.write(chunk)
        queue.task_done()


def create_tasks(number: int, coro: Callable, *args, **kwargs) -> List[Task]:
    """Функция создания задач"""
    return [asyncio.create_task(coro(*args, **kwargs)) for _ in range(number)]


async def main():
    number_of_images = 4
    session = aiohttp.ClientSession()
    pages_queue = asyncio.Queue()
    image_urls_queue = asyncio.Queue()

    page_getters = create_tasks(
        number=number_of_images, coro=get_image_page, queue=pages_queue,
        session=session
    )

    url_getters = create_tasks(
        number=number_of_images, coro=get_image_url, pages_queue=pages_queue,
        image_urls_queue=image_urls_queue, session=session
    )

    downloaders = create_tasks(
        number=number_of_images, coro=download_image, queue=image_urls_queue,
        session=session
    )

    await asyncio.gather(*page_getters)

    await pages_queue.join()
    for task in url_getters:
        task.cancel()

    await image_urls_queue.join()
    for task in downloaders:
        task.cancel()

    await session.close()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO, filename='logs.txt', encoding='UTF-8',
    )
    logger.info('Images upload started')
    asyncio.run(main())
    logger.info('Images upload finished')
