#!/usr/bin/python
# _*_ coding: utf-8 _*_

"""
根据筛选的段落，计算 start，end 下标

@author: Qing Liu, sunnymarkliu@163.com
@github: https://github.com/sunnymarkLiu
@time  : 2019/9/6 16:39
"""
import sys
sys.path.append('../')
import re
import json
from utils.rouge import RougeL


ans_pattern = re.compile(r'@content\d@')


def find_answer_in_docid(answer):
    docs = ans_pattern.findall(answer)
    return list(set([int(doc[-2:-1]) for doc in docs]))

def find_best_match_index(sub_text, doc_content):
    """
    找到 sub_text 在 content 覆盖度最大的开始和结束下标
    """
    if sub_text in doc_content:
        best_start = doc_content.index(sub_text)
        best_end = best_start + len(sub_text) - 1
        return best_start, best_end, 1

    if sub_text.endswith('。') and sub_text[:-1] in doc_content:
        sub_text = sub_text[:-1]
        best_start = doc_content.index(sub_text)
        best_end = best_start + len(sub_text) - 1
        return best_start, best_end, 1

    # 存在一些标注错误的样本，去掉空字符后才能定位
    if sub_text.replace(' ', '') in doc_content:
        sub_text = sub_text.replace(' ', '')
        best_start = doc_content.index(sub_text)
        best_end = best_start + len(sub_text) - 1
        return best_start, best_end, 1

    # 不能直接定位，利用覆盖率搜索
    support_para_chars = set(sub_text)

    best_score = 0
    best_start = -1
    best_end = -1

    last_end_in_sub_text = len(doc_content) - 1
    for start_idx in range(0, len(doc_content) - len(sub_text)):
        if doc_content[start_idx] not in support_para_chars:
            continue

        for end_idx in range(last_end_in_sub_text, start_idx - 1, -1):
            if doc_content[end_idx] not in support_para_chars:
                continue

            sub_para_content = doc_content[start_idx: end_idx + 1]
            score = RougeL().add_inst(cand=sub_para_content, ref=sub_text).get_score()

            if score > best_score:
                best_score = score
                best_start = start_idx
                best_end = end_idx
                last_end_in_sub_text = end_idx

    if best_score == 0:
        return -1, -1, 0
    else:
        return best_start, best_end, best_score

def calc_ceil_rougel(answer_text, sample):
    # 计算抽取的 fake answer 以及对应的 ceil rougel
    fake_answers = [sample['documents'][answer_label[0]]['content'][answer_label[1]: answer_label[2] + 1]
                    for answer_label in sample['answer_labels']]
    sample['fake_answers'] = fake_answers

    if len(fake_answers) == 0:
        sample['ceil_rougel'] = 0
    else:
        ceil_rougel = RougeL().add_inst(cand=''.join(fake_answers), ref=answer_text).get_score()
        sample['ceil_rougel'] = ceil_rougel

def gen_mrc_dataset(sample):
    """
    生成全文本下的 MRC 数据集
    """
    # 段落文本拼接成 content，以及对于的特征的合并
    for doc_id, doc in enumerate(sample['documents']):
        doc['content'] = ''.join(doc['paragraphs'])
        del doc['paragraphs']

    # 对训练集定位答案的 start end 下标
    if 'answer' not in sample:
        return

    # 根据 support paragraph 找到答案所在的 sub para
    support_para_in_docids = find_answer_in_docid(sample['supporting_paragraph'])

    supported_paras = {}    # {'support所在doc_id': [{'找到的最匹配的 support para', '最匹配的开始下标', '最匹配的结束下标'}]}
    for sup_para_in_docid in support_para_in_docids:
        para_strs = sample['supporting_paragraph'].split('@content{}@'.format(sup_para_in_docid))
        for para_str in para_strs:
            if para_str != '' and '@content' not in para_str:
                para_str = para_str.replace('content{}@'.format(sup_para_in_docid), '')
                sup_start, sup_end, rougel = find_best_match_index(para_str, sample['documents'][sup_para_in_docid - 1]['content'])
                found_sup_para = sample['documents'][sup_para_in_docid - 1]['content'][sup_start: sup_end + 1]
                # 同一个 doc 可能出现多个support para
                if sup_para_in_docid in supported_paras:
                    supported_paras[sup_para_in_docid].append((found_sup_para, sup_start, sup_end))
                else:
                    supported_paras[sup_para_in_docid] = [(found_sup_para, sup_start, sup_end)]

    answer = sample['answer']
    ans_in_docids = find_answer_in_docid(answer)
    answer_texts = []
    # 可能存在跨 doc 的答案（dureader中表现为多答案的形式）
    answer_labels = []
    for ans_in_docid in ans_in_docids:
        # 找到当前 doc 的支撑para信息，这些para中可能包含答案
        doc_support_paras = supported_paras[ans_in_docid]   # [{'找到的最匹配的 support para', '最匹配的开始下标', '最匹配的结束下标'}]

        # IMPORTANT:
        # 答案几乎都在 supporting_paragraph 中，所以进行答案定位的时候，需要先根据 supporting_paragraph 缩小答案的搜索范围，
        # 再在其中定位答案的实际开始和结束的下标，同时需要注意加上 supporting_paragraph 搜索下标的偏移 shifted_start
        answer_strs = answer.split('@content{}@'.format(ans_in_docid))
        for answer_str in answer_strs:
            answer_str = answer_str.strip()  # important
            # @content1@ 包裹的实际答案文本
            if answer_str != '' and '@content' not in answer_str:
                answer_str = answer_str.replace('content{}@'.format(ans_in_docid), '')
                answer_texts.append(answer_str)

                max_rougel = 0
                best_start_in_sup_para = -1
                best_end_in_sup_para = -1
                best_sup_para_i = None
                for sup_para_i, doc_support_para in enumerate(doc_support_paras):
                    start_in_sup_para, end_in_sup_para, rougel = find_best_match_index(answer_str, doc_support_para[0])
                    if rougel > max_rougel:
                        max_rougel = rougel
                        best_start_in_sup_para = start_in_sup_para
                        best_end_in_sup_para = end_in_sup_para
                        best_sup_para_i = sup_para_i

                if best_start_in_sup_para != -1 and best_end_in_sup_para != -1:
                    start_label = best_start_in_sup_para + doc_support_paras[best_sup_para_i][1]
                    end_label = start_label + (best_end_in_sup_para - best_start_in_sup_para)
                    answer_labels.append((ans_in_docid - 1, start_label, end_label))

        sample['answer_labels'] = answer_labels
        answer_text = ''.join(answer_texts)
        calc_ceil_rougel(answer_text, sample)


if __name__ == '__main__':
    for line in sys.stdin:
        if not line.startswith('{'):
            continue

        json_sample = json.loads(line.strip())

        gen_mrc_dataset(json_sample)
        print(json.dumps(json_sample, ensure_ascii=False))
