import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import CrossEntropyLoss
from pytorch_transformers import BertPreTrainedModel, BertModel

import sys
sys.path.append('..')
from nn.layers import Highway

VERY_NEGATIVE_NUMBER = -1e29


class BertForLes(BertPreTrainedModel):
    def __init__(self, config):
        super(BertForLes, self).__init__(config)
        self.num_labels = config.num_labels

        self.bert = BertModel(config)
        self.qa_outputs = nn.Linear(config.hidden_size, config.num_labels)

        self.apply(self.init_weights)

    def forward(self, input_ids, token_type_ids=None, attention_mask=None, start_positions=None,
                end_positions=None, position_ids=None, head_mask=None,
                input_span_mask=None):
        outputs = self.bert(input_ids, position_ids=position_ids, token_type_ids=token_type_ids,
                            attention_mask=attention_mask, head_mask=head_mask)
        sequence_output = outputs[0]

        logits = self.qa_outputs(sequence_output)
        start_logits, end_logits = logits.split(1, dim=-1)
        start_logits = start_logits.squeeze(-1)
        end_logits = end_logits.squeeze(-1)

        # 增加input_span_mask, 这里为None时会报错(防止特征没有load)
        adder = (1.0 - input_span_mask.float()) * VERY_NEGATIVE_NUMBER
        start_logits += adder
        end_logits += adder

        outputs = (start_logits, end_logits,) + outputs[2:]
        if start_positions is not None and end_positions is not None:
            # If we are on multi-GPU, split add a dimension
            if len(start_positions.size()) > 1:
                start_positions = start_positions.squeeze(-1)
            if len(end_positions.size()) > 1:
                end_positions = end_positions.squeeze(-1)
            # sometimes the start/end positions are outside our model inputs, we ignore these terms
            ignored_index = start_logits.size(1)
            start_positions.clamp_(0, ignored_index)
            end_positions.clamp_(0, ignored_index)

            loss_fct = CrossEntropyLoss(ignore_index=ignored_index)
            start_loss = loss_fct(start_logits, start_positions)
            end_loss = loss_fct(end_logits, end_positions)
            total_loss = (start_loss + end_loss) / 2
            outputs = (total_loss,) + outputs

        return outputs  # (loss), start_logits, end_logits, (hidden_states), (attentions)


class LesBertHighway(BertPreTrainedModel):
    def __init__(self, config):
        super(LesBertHighway, self).__init__(config)
        self.num_labels = config.num_labels

        self.bert = BertModel(config)

        # 加入特征后hidden_size会改变
        self.hidden_size = config.hidden_size

        # 增加doc_position特征
        self.doc_position_dim = 5
        self.hidden_size += self.doc_position_dim

        # 增加highway层
        self.highway = Highway(input_dim=self.hidden_size, num_layers=2)

        self.qa_outputs = nn.Linear(self.hidden_size, config.num_labels)

        self.apply(self.init_weights)

    def forward(self, input_ids, token_type_ids=None, attention_mask=None, start_positions=None,
                end_positions=None, position_ids=None, head_mask=None,
                input_span_mask=None, doc_position=None):
        outputs = self.bert(input_ids, position_ids=position_ids, token_type_ids=token_type_ids,
                            attention_mask=attention_mask, head_mask=head_mask)
        sequence_output = outputs[0]

        # 增加doc_position特征
        doc_position = F.one_hot(doc_position, num_classes=self.doc_position_dim)  # (B,5)
        doc_position = doc_position.unsqueeze(1).expand(-1, sequence_output.size(1), -1)  # (B,L,5)
        sequence_output = torch.cat([sequence_output, doc_position.float()], dim=-1)  # (B,L,D+5)

        # 增加highway层
        sequence_output = self.highway(sequence_output)

        logits = self.qa_outputs(sequence_output)
        start_logits, end_logits = logits.split(1, dim=-1)
        start_logits = start_logits.squeeze(-1)
        end_logits = end_logits.squeeze(-1)

        # 增加input_span_mask, 这里为None时会报错(防止特征没有load)
        adder = (1.0 - input_span_mask.float()) * VERY_NEGATIVE_NUMBER
        start_logits += adder
        end_logits += adder

        outputs = (start_logits, end_logits,) + outputs[2:]
        if start_positions is not None and end_positions is not None:
            # If we are on multi-GPU, split add a dimension
            if len(start_positions.size()) > 1:
                start_positions = start_positions.squeeze(-1)
            if len(end_positions.size()) > 1:
                end_positions = end_positions.squeeze(-1)
            # sometimes the start/end positions are outside our model inputs, we ignore these terms
            ignored_index = start_logits.size(1)
            start_positions.clamp_(0, ignored_index)
            end_positions.clamp_(0, ignored_index)

            loss_fct = CrossEntropyLoss(ignore_index=ignored_index)
            start_loss = loss_fct(start_logits, start_positions)
            end_loss = loss_fct(end_logits, end_positions)
            total_loss = (start_loss + end_loss) / 2
            outputs = (total_loss,) + outputs

        return outputs  # (loss), start_logits, end_logits, (hidden_states), (attentions)


# class LesBertAOA(BertPreTrainedModel):
#     def __init__(self, config):
#         super(LesBertAOA, self).__init__(config)
#         self.num_labels = config.num_labels
#
#         self.bert = BertModel(config)
#         self.qa_outputs = nn.Linear(config.hidden_size, config.num_labels)
#
#         self.max_query_len = 64
#
#         self.apply(self.init_weights)
#
#     def forward(self, input_ids, token_type_ids=None, attention_mask=None, start_positions=None,
#                 end_positions=None, position_ids=None, head_mask=None,
#                 input_span_mask=None):
#         outputs = self.bert(input_ids, position_ids=position_ids, token_type_ids=token_type_ids,
#                             attention_mask=attention_mask, head_mask=head_mask)
#         sequence_output = outputs[0]
#
#         logits = self.qa_outputs(sequence_output)
#         start_logits, end_logits = logits.split(1, dim=-1)
#         start_logits = start_logits.squeeze(-1)
#         end_logits = end_logits.squeeze(-1)
#
#         # 增加Attention-Over-Attention
#         # 1. 得到matrix和mask
#         aoa_attention_matrix = torch.bmm(sequence_output[:, :self.max_query_len, :], sequence_output.transpose(1, 2))  # (B,64,512)
#         aoa_attention_matrix = aoa_attention_matrix[:, 1:, :]  # (B,63,512)
#         aoa_mask = input_span_mask[:, :self.max_query_len].unsqueeze(2) ^ input_span_mask.unsqueeze(1)  # (B,64,512)
#         aoa_mask = aoa_mask[:, 1:, :]  # (B,63,512)
#         for batch_id in range(aoa_mask.size(0)):
#             for i in range(aoa_mask.size(1)):
#                 if aoa_mask[batch_id][i][0].item() == 0:
#                     aoa_mask[batch_id][i:] = 0
#                     break
#         aoa_adder = (1.0 - aoa_mask.float()) * -10000.0  # (B,63,512)
#         aoa_attention_matrix += aoa_adder
#
#         # 2. 计算attention, matrix第0维代表batch, 第1维代表query,第2维代表document
#         q2c = F.softmax(aoa_attention_matrix, dim=2)  # (B,63,512)
#         c2q = F.softmax(aoa_attention_matrix, dim=1).mean(dim=2, keepdim=True)  # (B,63,1)
#         aoa_attention = torch.sum(q2c * c2q, dim=1)  # (B,512)
#
#         # 增加input_span_mask, 这里为None时会报错(防止特征没有load)
#         adder = (1.0 - input_span_mask.float()) * -10000.0
#         start_logits += adder
#         end_logits += adder
#
#         # 用AOA对Logit进行mask
#         start_logits *= aoa_attention
#         end_logits *= aoa_attention
#
#         outputs = (start_logits, end_logits,) + outputs[2:]
#         if start_positions is not None and end_positions is not None:
#             # If we are on multi-GPU, split add a dimension
#             if len(start_positions.size()) > 1:
#                 start_positions = start_positions.squeeze(-1)
#             if len(end_positions.size()) > 1:
#                 end_positions = end_positions.squeeze(-1)
#             # sometimes the start/end positions are outside our model inputs, we ignore these terms
#             ignored_index = start_logits.size(1)
#             start_positions.clamp_(0, ignored_index)
#             end_positions.clamp_(0, ignored_index)
#
#             loss_fct = CrossEntropyLoss(ignore_index=ignored_index)
#             start_loss = loss_fct(start_logits, start_positions)
#             end_loss = loss_fct(end_logits, end_positions)
#             total_loss = (start_loss + end_loss) / 2
#             outputs = (total_loss,) + outputs
#
#         return outputs  # (loss), start_logits, end_logits, (hidden_states), (attentions)


class LesAnswerVerification(BertPreTrainedModel):
    def __init__(self, config):
        super(LesAnswerVerification, self).__init__(config)
        self.num_labels = config.num_labels

        self.bert = BertModel(config)
        self.qa_outputs = nn.Linear(config.hidden_size, config.num_labels)

        # 答案验证相关
        self.retionale_outputs = nn.Linear(config.hidden_size, 1)
        self.beta = 100

        self.apply(self.init_weights)

    def forward(self, input_ids, token_type_ids=None, attention_mask=None, start_positions=None,
                end_positions=None, position_ids=None, head_mask=None,
                input_span_mask=None):
        outputs = self.bert(input_ids, position_ids=position_ids, token_type_ids=token_type_ids,
                            attention_mask=attention_mask, head_mask=head_mask)
        sequence_output = outputs[0]

        ## 答案验证相关
        batch_size = sequence_output.size(0)
        seq_length = sequence_output.size(1)
        hidden_size = sequence_output.size(2)
        sequence_output_matrix = sequence_output.view(batch_size * seq_length, hidden_size)
        rationale_logits = self.retionale_outputs(sequence_output_matrix)  # (B*L,1)
        rationale_logits = torch.sigmoid(rationale_logits)  # (B*L,1)
        rationale_logits = rationale_logits.view(batch_size, seq_length)  # (B,L)
        final_hidden = sequence_output * rationale_logits.unsqueeze(2)  # (B,L,H)
        # sequence_output = final_hidden.view(batch_size * seq_length, hidden_size)  # (B*L,H)
        sequence_output = final_hidden

        logits = self.qa_outputs(sequence_output)
        start_logits, end_logits = logits.split(1, dim=-1)
        start_logits = start_logits.squeeze(-1)
        end_logits = end_logits.squeeze(-1)

        # 增加rationale gate
        rationale_logits = rationale_logits * attention_mask.float()
        start_logits = start_logits * rationale_logits
        end_logits = end_logits * rationale_logits

        # 增加input_span_mask, 这里为None时会报错(防止特征没有load)
        adder = (1.0 - input_span_mask.float()) * VERY_NEGATIVE_NUMBER
        start_logits += adder
        end_logits += adder

        outputs = (start_logits, end_logits,) + outputs[2:]
        if start_positions is not None and end_positions is not None:
            # If we are on multi-GPU, split add a dimension
            if len(start_positions.size()) > 1:
                start_positions = start_positions.squeeze(-1)
            if len(end_positions.size()) > 1:
                end_positions = end_positions.squeeze(-1)
            # sometimes the start/end positions are outside our model inputs, we ignore these terms
            ignored_index = start_logits.size(1)
            start_positions.clamp_(0, ignored_index)
            end_positions.clamp_(0, ignored_index)

            # rationale_positions = token_type_ids.float()
            # alpha = 0.25
            # gamma = 2.
            # rationale_loss = -alpha * ((1 - rationale_logits) ** gamma) * rationale_positions * torch.log(
            #     rationale_logits + 1e-8) - (1 - alpha) * (rationale_logits ** gamma) * (
            #     1 - rationale_positions) * torch.log(1 - rationale_logits + 1e-8)
            # rationale_loss = (rationale_loss * token_type_ids.float()).sum() / token_type_ids.float().sum()

            loss_fct = CrossEntropyLoss(ignore_index=ignored_index)
            start_loss = loss_fct(start_logits, start_positions)
            end_loss = loss_fct(end_logits, end_positions)
            total_loss = (start_loss + end_loss) / 2
            outputs = (total_loss,) + outputs

        return outputs  # (loss), start_logits, end_logits, (hidden_states), (attentions)


class MultiLinearLayer(nn.Module):
    def __init__(self, layers, hidden_size, output_size, activation=None):
        super(MultiLinearLayer, self).__init__()
        self.net = nn.Sequential()

        for i in range(layers - 1):
            self.net.add_module(str(i) + 'linear', nn.Linear(hidden_size, hidden_size))
            self.net.add_module(str(i) + 'relu', nn.ReLU(inplace=True))

        self.net.add_module('linear', nn.Linear(hidden_size, output_size))

    def forward(self, x):
        return self.net(x)
