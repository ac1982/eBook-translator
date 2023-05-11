import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import tiktoken
import json
import argparse
from openai_translator import translate_content
import sys
import os
import concurrent

# 加载配置文件
with open("config.json", "r") as f:
    config = json.load(f)

# 根据配置文件中的模型名称设置 MAX_TOKENS
model_name = config['model']
if model_name == "gpt-4":
    MAX_TOKENS = 2400
elif model_name == "gpt-3.5-turbo":
    MAX_TOKENS = 1200
else:
    print(f"未知模型: {model_name}")
    sys.exit(1)

ENCODING_NAME = "cl100k_base"
THRESHOLD = MAX_TOKENS/2
total_tokens = 0
max_workers = config.get('max_workers', None)

if max_workers is None:
    max_workers = os.cpu_count()


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(config['model'])
    num_tokens = len(encoding.encode(string))
    return num_tokens

# 使用递归的方法翻译超过MAX_TOKENS的内容
def translate_recursive(soup, level=1):
    # 检查 soup 是否为空
    if not soup:
        # 如果为空,返回空字符串和0
        return '', 0

    children = list(soup.children)  # 获取 soup 的子节点列表
    children_number = len(children)  # 计算子节点的数量
    if config['test']:
        print(f"Level {level} 的子节点(Children)数量{children_number}")

    translated_content = ''  # 初始化翻译后的内容字符串
    cost_tokens = 0  # 初始化已用 tokens 数量
    buffer = ''  # 初始化缓冲区字符串
    buffer_tokens = 0  # 初始化缓冲区 tokens 数量

    # 避免错误导致的无限递归
    if level == 5:
        print(f"递归层数超过{level}层，停止程序。")
        sys.exit(1)

    for i,child in enumerate(children):  # 遍历子节点
        child_html = str(child)  # 将子节点转换为 HTML 字符串
        child_tokens = num_tokens_from_string(child_html)  # 计算子节点的 tokens 数量
        if child_tokens < MAX_TOKENS:
            # 如果子节点的 token 数量大于 THRESHOLD，先清空缓冲区，然后直接处理 child_html
            if child_tokens >= THRESHOLD:
                if buffer:
                    if config['test']:
                        print(
                            f"处理Level:{level} 第{i+1} 子节点是有buffer。\n合计Tokens：{buffer_tokens} \n翻译组合内容: \n{buffer}\n")
                    translated_buffer, buffer_cost_tokens = translate_content(
                        buffer)
                    translated_content += translated_buffer
                    cost_tokens += buffer_cost_tokens
                    buffer = ''
                    buffer_tokens = 0

                if config['test']:
                    print(
                        f"该Level:{level} 第{i+1} 子节点 tokens：{child_tokens} 直接处理")
                translated_child, child_cost_tokens = translate_content(child_html)
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
                            f"该Level:{level} 第{i+1} 子节点,把其添加到的buffer后，Tokens超过Threshold。\nTokens：{buffer_tokens} \n翻译组合内容: \n{buffer}\n")
                    translated_buffer, buffer_cost_tokens = translate_content(buffer)
                    translated_content += translated_buffer
                    cost_tokens += buffer_cost_tokens
                    buffer = ''
                    buffer_tokens = 0
        else:
            # 先清空缓冲区
            if buffer:
                if config['test']:
                    print(f"该Level:{level} 第{i+1} 子节点 大于MAX_TOKENS \n合计Tokens：{buffer_tokens} \n清空buffer后递归处理,Buffer: \n{buffer} \n")
                translated_buffer, buffer_cost_tokens = translate_content(
                    buffer)
                translated_content += translated_buffer
                cost_tokens += buffer_cost_tokens
                buffer = ''
                buffer_tokens = 0

            # 递归处理子节点
            translated_child, child_cost_tokens = translate_recursive(child, level + 1)
            translated_content += translated_child
            cost_tokens += child_cost_tokens

    # 处理剩余的缓冲区内容
    if buffer:
        if config['test']:
            print(f"遍历ITEM结束，缓冲区仍有Buffer，合计tokens：{buffer_tokens} \n翻译Buffer: \n{buffer}\n")
        translated_buffer, buffer_cost_tokens = translate_content(buffer)
        translated_content += translated_buffer
        cost_tokens += buffer_cost_tokens

    return translated_content, cost_tokens  # 返回翻译后的内容和已用 tokens 数量



# item 是 ebooklib book.get_items()的子内容，通常是html字符串
def translate_item(content):
    # global total_tokens  # 使用全局变量 total_tokens 来跟踪已翻译的 tokens 数量
    count = num_tokens_from_string(content)  # 计算输入内容的 tokens 数量
    item_cost_tokens=0
    if config['test']:
        print(f"该 ITEM 的tokens合计：{count}")

    if count < MAX_TOKENS:
        # 如果输入内容的 tokens 数量小于 MAX_TOKENS
        if config['test']:
            print("Translating the entire content.\n")
        new_item_content, cost_tokens = translate_content(content)  # 直接翻译整个内容
        item_cost_tokens += cost_tokens  # 累加已用 tokens 数量
    else:
        # 如果输入内容的 tokens 数量大于 MAX_TOKENS，需要逐部分翻译
        if config['test']:
            print("Translating the content by parts.\n")
        soup = BeautifulSoup(content, 'html.parser')  # 使用 BeautifulSoup 解析 HTML 内容
        translated_body, cost_tokens = translate_recursive(soup.body)  # 递归地翻译子元素
        item_cost_tokens += cost_tokens  # 累加已用 tokens 数量
        # 将翻译后的 body 内容替换原始 soup 对象中的 body 内容
        soup.body.clear()  # 清空原始 soup 对象中的 body 内容
        soup.body.append(BeautifulSoup(translated_body, 'html.parser'))  # 将翻译后的内容添加到 soup 的 body 中
        new_item_content = str(soup)  # 获取整个 HTML 字符串（包括翻译后的内容）

    return new_item_content, item_cost_tokens  # 返回翻译后的内容


if __name__ == '__main__':
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    
    parser = argparse.ArgumentParser(description='Translate an EPUB file.')
    parser.add_argument('input_file', type=str,
                        help='The path to the input EPUB file.')

    args = parser.parse_args()
    try:
        book = epub.read_epub(args.input_file)
    except FileNotFoundError:
        print(f"文件 '{args.input_file}' 不存在，请检查文件名和路径是否正确。")
        sys.exit(1)

    new_book = epub.EpubBook()

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
    items = list(book.get_items())
    total_items = len(items)
    
    item_results = {}
    item_futures = []
    total_tokens = 0

    for index, item in enumerate(items):
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            item_count += 1
            if config['test'] and item_count > max(1, total_items // 10):
                #测试环境只加载1/10的ITEMS
                break

            original_content = item.get_content().decode('utf-8')
            future = executor.submit(translate_item, original_content)
            item_futures.append((index, item, future))

    for index, item, future in item_futures:
        new_content, item_cost_tokens = future.result()
        total_tokens += item_cost_tokens
        item_results[index] = (new_content, item_cost_tokens)

    for index, item in enumerate(items):
        if index in item_results:
            new_content, _ = item_results[index]
            new_item = epub.EpubItem(uid=item.id, file_name=item.file_name,
                                     media_type=item.media_type, content=new_content)
            new_book.add_item(new_item)
            # Update TOC
            for toc_entry in new_book.toc:
                if toc_entry.href == item.file_name:
                    toc_entry.item = new_item
        else:
            new_book.add_item(item)

    new_book.toc = book.toc
    new_book.spine = book.spine
    new_book.guide = book.guide

    output_file = args.input_file.split('.')[0] + '_zh.epub'
    epub.write_epub(output_file, new_book)
    usd_dollar = (total_tokens/1000)*0.002
    print(f"Cost tokens: {usd_dollar:.2f} USD")
