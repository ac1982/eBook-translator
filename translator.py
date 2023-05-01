import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import tiktoken
import json
import argparse
from openai_translator import translate_content
from tqdm import tqdm
import sys

MAX_TOKENS = 1200
ENCODING_NAME = "cl100k_base"
THRESHOLD = 800
total_tokens = 0


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(config['model'])
    num_tokens = len(encoding.encode(string))
    return num_tokens


def translate_helper(soup, level=1):
    global total_tokens

    if not soup:
        return '', 0

    children = list(soup.children)
    children_number = len(children)
    if config['test']:
        print(f"Level {level} 的chilren 数量{children_number}")

    i = 0
    translated_content = ''
    cost_tokens = 0
    buffer = ''
    buffer_tokens = 0

    if level == 5:
        sys.exit(1)

    for child in children:
        i += 1
        child_html = str(child)

        # 如果子节点是空字符，那么直接略过
        if child_html.strip() == "":
            if config['test']:
                print(f"该level {level} 第{i} 子节点 空字符")
            continue

        child_tokens = num_tokens_from_string(child_html)

        if child_tokens < MAX_TOKENS:
            # 如果子节点的 token 数量大于 THRESHOLD，先清空缓冲区，然后直接处理 child_html
            if child_tokens >= THRESHOLD:
                if buffer:
                    if config['test']:
                        print(
                            f"该level {level} 第{i} 子节点是有buffer：{buffer_tokens} 翻译组合内容: {buffer}")
                    translated_buffer, buffer_cost_tokens = translate_content(
                        buffer)
                    translated_content += translated_buffer
                    cost_tokens += buffer_cost_tokens
                    buffer = ''
                    buffer_tokens = 0

                if config['test']:
                    print(
                        f"该level {level} 第{i} 子节点 tokens：{child_tokens} 直接处理")
                translated_child, child_cost_tokens = translate_content(
                    child_html)
                translated_content += translated_child
                cost_tokens += child_cost_tokens

            # 如果子节点的 token 数量小于 THRESHOLD
            else:
                # 将较小的子节点添加到缓冲区，并累加 buffer_tokens
                buffer += child_html
                buffer_tokens += child_tokens
                # 如果添加后缓冲区超过THRESHOLD，那么清空缓冲区
                if buffer_tokens >= THRESHOLD:
                    if config['test']:
                        print(
                            f"该level {level} 第{i} 子节点的buffer tokens：{buffer_tokens} 翻译组合内容: {buffer}")
                    translated_buffer, buffer_cost_tokens = translate_content(
                        buffer)
                    translated_content += translated_buffer
                    cost_tokens += buffer_cost_tokens
                    buffer = ''
                    buffer_tokens = 0
        else:
            # 先清空缓冲区
            if buffer:
                if config['test']:
                    print(
                        f"该level {level} tokens：{buffer_tokens} 翻译组合内容: {buffer}")
                translated_buffer, buffer_cost_tokens = translate_content(
                    buffer)
                translated_content += translated_buffer
                cost_tokens += buffer_cost_tokens
                buffer = ''
                buffer_tokens = 0

            # 递归处理子节点
            translated_child, child_cost_tokens = translate_helper(
                child, level + 1)
            translated_content += translated_child
            cost_tokens += child_cost_tokens

    # 处理剩余的缓冲区内容
    if buffer:
        if config['test']:
            print(f"该level {level} tokens：{buffer_tokens} 翻译组合内容: {buffer}")
        translated_buffer, buffer_cost_tokens = translate_content(buffer)
        translated_content += translated_buffer
        cost_tokens += buffer_cost_tokens

    return translated_content, cost_tokens


def translate(content):
    global total_tokens
    count = num_tokens_from_string(content)  # 计算输入内容的 token 数量
    if config['test']:
        print(f"该item本地计算的tokens合计：{count}")

    # 如果输入内容的 token 数量小于 MAX_TOKENS
    if count < MAX_TOKENS:
        if config['test']:
            print("Translating the entire content...")
        new_content, cost_tokens = translate_content(content)  # 直接翻译整个内容
        total_tokens += cost_tokens  # 累加已用 token 数量
    else:  # 如果输入内容的 token 数量大于 MAX_TOKENS
        if config['test']:
            print("Translating the content by parts...")
        # 使用 BeautifulSoup 解析 HTML 内容
        soup = BeautifulSoup(content, 'html.parser')
        translated_body, cost_tokens = translate_helper(soup.body)  # 递归地翻译子元素
        total_tokens += cost_tokens

        # 将翻译后的 body 内容替换原始 soup 对象中的 body 内容
        soup.body.clear()
        soup.body.append(BeautifulSoup(translated_body, 'html.parser'))
        new_content = str(soup)  # 获取整个 HTML 字符串

    return new_content  # 返回翻译后的内容


if __name__ == '__main__':
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Translate an EPUB file.')
    parser.add_argument('input_file', type=str,
                        help='The path to the input EPUB file.')

    # Parse the command line arguments
    args = parser.parse_args()
    try:
        book = epub.read_epub(args.input_file)
    except FileNotFoundError:
        print(f"文件 '{args.input_file}' 不存在，请检查文件名和路径是否正确。")
        sys.exit(1)

    new_book = epub.EpubBook()

    with open('config.json', 'r') as f:
        config = json.load(f)

    dc_keys = ['identifier', 'title', 'language', 'creator', 'contributor',
               'publisher', 'rights', 'coverage', 'date', 'description']
    for key in dc_keys:
        metadata = book.get_metadata('DC', key)
        for entry in metadata:
            new_book.add_metadata('DC', key, entry[0], others=entry[1])

    custom_metadata = book.get_metadata('OPF', None)
    for entry in custom_metadata:
        if 'name' in entry[1] and 'content' in entry[1]:
            new_book.add_metadata(
                'OPF', entry[1]['name'], entry[1]['content'], others=entry[1])

    item_count = 0
    # Convert items to a list and get the total count
    items = list(book.get_items())
    total_items = len(items)
    for item in tqdm(items, total=total_items, desc="Processing items", unit="item"):
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            item_count += 1
            if config['test'] and item_count > 7:
                break

            original_content = item.get_content().decode('utf-8')
            new_content = translate(original_content)
            new_item = epub.EpubItem(uid=item.id, file_name=item.file_name,
                                     media_type=item.media_type, content=new_content)
            new_book.add_item(new_item)
        else:
            # Add the item directly to
            # Add the item directly to the new book object
            new_book.add_item(item)

    # Copy the chapter structure, table of contents, and guide
    new_book.toc = book.toc
    new_book.spine = book.spine
    new_book.guide = book.guide

    # Save the new book to a new EPUB file
    output_file = args.input_file.split('.')[0] + '_zh.epub'
    epub.write_epub(output_file, new_book)
    usd_dollar = (total_tokens/1000)*0.002
    print(f"Cost tokens: {total_tokens}, may be ${usd_dollar} ")
