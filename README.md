# Ebook-Translator: 
![eBook-GPT-Translator Logo](./logo.png)
Ebook-Translator 是一个基于GPT的小项目用来翻译电子书，目前仅支持epub格式。若是其他格式电子书，可以先用Calibre转换后再翻译。Ebook-Translator is a small project based on GPT that can translate ebooks, currently only supporting epub format. If the ebook is in another format, you can use Calibre to convert it before translating.

## 特点 Features

- 保留电子书的原始格式，包括目录、图片、摘要、引用、斜体、粗体、链接等
- Preserve the original format of the e-book, including table of contents, images, summary, quotes, italics, bold, links, etc.
- AI原生的工程，您可以修改提示和温度来调整翻译结果，让翻译结果符合自己理解的“信·达·雅”
- AI-native engineering, you can modify the prompts and temperature to adjust the translation results, so that the translation results match your own understanding of "faithfulness, expressiveness, elegance"
- 对俚语和生僻内容提供译者注
- Provide translator's notes for slang and obscure content


## 为什么需要这个项目？Why need this project?
- 现有的翻译方案无法保留原始格式
- The existing translation solutions cannot preserve the original format
- 通过深度使用GPT，探索 GPT的边界，以及作为人类的一员，我自己的边界在哪里
- By extensively using GPT, I am exploring the boundaries of GPT, as well as where my own boundaries lie as a human being

## 使用方法 How to use
```bash
git clone https://github.com/ac1982/eBook-translator.git
cd eBook-translator
pip install -r requrements.txt
mv config_example.json config.json
```
把你自己的OpenAI-API-Key，通常是```sk-```开头的一串字符，填写到```config.json```里面的```openai_api_key```。
Fill in your OpenAI API key, which usually starts with ```sk-```, into the ```openai_api_key``` field inside the ```config.json``` file.
```bash
python translator.py your_ebook.epub
```
我们进一步说明下```config.json```各个参数的意思
```
"openai_api_key": "sk-your-key-here",// 填写你的OpenAI API Key
"model": "gpt-3.5-turbo", //支持gpt-4 或 gpt-3.5-turbo
"system": "GPT Chat 的最高级提示词放在这里，如果你不知道它做什么的，保留默认值",
"max_workers": null, //本项目支持多进程，所以可以并发来提高效率并且保留顺序，默认值是当前机器的CPU核心数
"test": false //如果设置成true，只是处理items_number的数量
"items_number": 7 //默认是7，仅当test模式为true的时候有效，用作处理items的数量，通常5-7比较合理
```