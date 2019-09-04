#!/usr/bin/python
# _*_ coding: utf-8 _*_

"""

@author: Qing Liu, sunnymarkliu@163.com
@github: https://github.com/sunnymarkLiu
@time  : 2019/9/3 21:59
"""
import re
import sys
import json
import collections

# --------------- remove space ---------------
spaces = {'\x10', '\x7f', '\x9d', '\xad', '\x0a', '\xa0', '\x0d', '\u001d', '\u0007', '\u001f', '\u000f',
          '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007', '\u0008', '\u0009',
          '\u0010', '\u0011', '\u0012', '\u0013', '\u0014', '\u0015', '\u0016', '\u0017', '\u0018',
          '\f', '\n', '\r', '\t', '\v', '&#160;', '&nbsp;', '\\uDDEF', '\\uDDEE', '\\uDDE8', '\\uDDF3', '\\u0001',
          '\\uD83C', '\\uDDFA', '\\uD83C', '\\uDDF8', '\\uDDEA', '\\uDDF7', '\\uDDF5', '\\uDDF3',
          '\u200b', '\u200e', '\u202a', '\u202c', '\ufeff', '\uf0d8', '\u2061', '\u1680', '\u180e',
          '\u2000', '\u2001', '\u2002', '\u2003', '\u2004', '\u2005', '\u2006', '\u2007', '\u2008',
          '\u2009', '\u200a', '\u2028', '\u2029', '\u202f', '\u205f', '\u3000'}


def remove_unicode_space(text):
    for space in spaces:
        text = text.replace(space, '')
    text = re.sub('\s+', ' ', text)
    return text

# --------------- remove url ---------------
URL_REGEX1 = r"""(?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:\'\".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)\b/?(?!@)))"""
URL_REGEX2 = r'[^\u4e00-\u9fa5|[$-_@.&+]]*(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

def remove_url_links(text):
    text = re.sub(URL_REGEX1, '', text)
    text = re.sub(URL_REGEX2, '', text)
    return text

# --------------- remove html tag ---------------
html_pattern = re.compile(r'<.*?>')
zhPattern = re.compile(u'[\u4e00-\u9fa5]+')

def remove_html_tag(text):
    text = re.sub('<{2,}', '', text)  # <<<
    # <> 中包含中文的
    text = re.sub('<；；', '', text)
    text = re.sub('([\u4e00-\u9fa5]+)>', '\g<1>', text)
    text = re.sub('<([\u4e00-\u9fa5]+)>', '\g<1>', text)
    tags = html_pattern.findall(text)

    new_tags = set()
    for tag in tags:
        match = zhPattern.search(tag)
        if not match:
            new_tags.add(tag)

    for html_tag in new_tags:
        text = text.replace(html_tag, '')

    return text

# --------------- remove duplacte chars ---------------
def clean_duplacte_chars(text):
    """
    去除很多重复的词和标点符号
    """
    reg = r'([^0-9IX]+)(\1){2,}'
    for i in range(6):
        temp = text
        text = re.sub(reg, lambda m: m.group(1), text)
        if len(text) == len(temp):
            break
    return text

remove_regx_map = collections.OrderedDict({
    r'\s+': ' ',
    r'<(\d+)>': '\g<1>',
    r'\^[A-Z]': '',  # '^G', '^H', '^E'去除
    r'(\!|\"|\#|\$|\%|\&|\'|\(|\)|\*|\+|\,|\-|\.|\/|\:|\;|\<|\=|\>|\?|\@|\[|\\|\]|\^|\_|\`|\{|\||\}|\~)\1{1,}': '\g<1>',
    r'("""|＃|＄|％|＆|＇|（|）|＊|＋|，|－|／|：|；|＜|＝|＞|＠|［|＼|］|＾|＿|｀|｛|｜|｝|～|｟|｠|｢|｣|､|　|、|〃|〈|〉|《|》|'
    r'「|」|『|』|【|】|〔|〕|〖|〗|〘|〙|〚|〛|〜|〝|〞|〟|〰|〾|〿|–|—|‘|’|‛|“|”|„|‟|…|‧|﹏|﹑|﹔|·|！|？|｡|。)\1{1,}': '\g<1>',
})

def remove_by_regex(text):
    text = text.strip()
    for rgx in remove_regx_map:
        text = re.sub(rgx, remove_regx_map[rgx], text)
    return text


def clean_text(text):
    text = remove_by_regex(
        clean_duplacte_chars(
            remove_url_links(
                remove_html_tag(
                    remove_unicode_space(text)
                )
            )
        )
    )
    return text


def clean_sample(sample):
    sample['question'] = clean_text(sample['question'])
    sample['keyword'] = clean_text(sample['keyword'])
    if 'supporting_paragraph' in sample:
        sample['supporting_paragraph'] = clean_text(sample['supporting_paragraph'])

    for document in sample['documents']:
        document['paragraphs'] = [clean_text(para) for para in document['paragraphs']]
        document['title'] = clean_text(document['title'])

        # 去除空段落和重复段落
        new_paras = []
        for para in document['paragraphs']:
            if para != '' and para not in new_paras:
                new_paras.append(para)
        document['paragraphs'] = new_paras

if __name__ == '__main__':
    for line in sys.stdin:
        if not line.startswith('{'):
            continue

        sample = json.loads(line.strip())
        clean_sample(sample)
        print(json.dumps(sample, ensure_ascii=False))
