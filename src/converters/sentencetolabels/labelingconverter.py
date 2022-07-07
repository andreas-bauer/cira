from dataclasses import dataclass

from torch import Tensor

from src.data.labels import Label, EventLabel, SubLabel
import src.util.constants as constants

@dataclass
class TokenLabel:
    begin: int
    end: int
    event: bool
    name: str

def convert(sentence_tokens: list[str], predictions: Tensor) -> list[Label]: 
    """Convert the list of sentence tokens and the list of predictions into a list of label objects
    
    parameters: 
        sentence_tokens -- list of tokens of the labeled sentence (words) as produced by the labeler
        predictions -- matrix of predictions (valid labels for each token)
        labels -- list of labels in the same order as in the predictions tensor
        
    returns: list of actual labels on the sentence"""
    # convert the list of sentence tokens, predictions, and labels into a list of token labels, where each token is associated with up to two labels
    token_labels = get_token_labeling(sentence_tokens=sentence_tokens, predictions=predictions)
    
    # merge all adjacent labels
    labels: list[Label] = merge_labels(token_labels=token_labels)

    # connect first-level and second-level labels with each other
    connect_labels(labels)

    return labels

def get_token_labeling(sentence_tokens: list[str], predictions: Tensor) -> list[TokenLabel]:
    """Convert the list of sentence tokens, predictions, and label ids into a list of tokens associated to all available labels
    
    parameters: 
        sentence_tokens -- list of sentence tokens (usually one token per word or special character)
        predictions -- list of predictions for each token, associating each available label with a weight within [0;1]
        labels -- ordered list of labels corresponding to the predictions
    
    returns: list of token labels, containing one object for each token label (max 2 per token)
    """
    token_labels: list[TokenLabel] = []
    cursor = 0

    for token_prediction_idx, token_prediction in enumerate(predictions[0]):
        # get the current token
        token: str = sentence_tokens[token_prediction_idx]
        token = token.replace("Ġ", "")

        # skip the initializing token
        if token == '<s>':
            continue
        # stop once a finalizing token is reached
        if token in ['</s>', '<pad>', '<sep>']:
            break

        # get all labels associated to a token
        for label_prediction_idx, label_prediction in enumerate(token_prediction):
            if label_prediction == 1:
                #token_predicted_labels.append(label_ids_verbose[label_prediction_idx]) 
                label = constants.LABEL_IDS_VERBOSE[label_prediction_idx]
                if label != 'notrelevant':
                    token_labels.append(TokenLabel(
                        begin=cursor, 
                        end=cursor+len(token), 
                        event = 'Cause' in label or 'Effect' in label, 
                        name=label))

        # advance the cursor to the position of the next token in the sentence
        cursor += advance_cursor(token)
        
    return token_labels

def merge_labels(token_labels: list[TokenLabel]) -> list[Label]:
    """Convert the list of token labels, where every single token is associated to up to two labels, to a list of merged labels, where each label spans all tokens that belong to the same label.

    parameters:
        token_labels -- list of each token within the sentence associated to up to two labels
        labels -- list of used labels in order

    returns:
        list of merged labels 
    """
    merged_labels: list[Label] = []
    id_counter = 0
    # keep track of event borders (begin and end of an event label)
    event_borders = []

    for ltype in constants.LABEL_IDS_VERBOSE:
        # get all labels of that type in the list of token labels
        all_of_type = [tl for tl in token_labels if tl.name==ltype]
        
        # merge adjacent token labels with one exception: if two second-level labels (Variable or Condition) are adjacent, but both belong to two different first-level (event) labels (Cause1/2/3, Event1/2/3), don't merge them
        if len(all_of_type) > 1:
            for index in range(len(all_of_type)-1, 0, -1):
                if all_of_type[index].begin - all_of_type[index-1].end <= 1 and \
                        all_of_type[index].begin not in event_borders and \
                        all_of_type[index-1].end not in event_borders:
                    b = all_of_type.pop(index)
                    a = all_of_type.pop(index-1)
                    merged = TokenLabel(begin=a.begin, end=b.end, event=a.event, name=a.name)
                    all_of_type.insert(index-1, merged)
                    
        for l in all_of_type:
            idv = f'L{id_counter}'
            label: Label = None
            if l.name[:-1] in ['Cause', 'Effect']:
                label = EventLabel(id=idv, name=l.name, begin=l.begin, end=l.end)
                event_borders.extend([l.begin, l.end])
            else:
                label = SubLabel(id=idv, name=l.name, begin=l.begin, end=l.end)
            merged_labels.append(label)
            id_counter += 1

    return merged_labels

def connect_labels(labels: list[Label]) -> None:
    """Connect event labels with their connected child labels and their neighbors
    
    parameters:
        labels -- list of unconnected labels (both EventLabels and SubLabels)
    """
    event_labels: list[EventLabel] = [label for label in labels if type(label) == EventLabel]
    
    for event_label in event_labels:
        children = [label for label in labels if (type(label) == SubLabel and label.begin >= event_label.begin and label.end <= event_label.end)]
        for child in children:
            event_label.add_child(child)

    # assign neighboring event labels as predecessor and successor of each other
    event_labels.sort(key=(lambda l: l.begin), reverse=False)
    for index, _ in enumerate(event_labels[:-1]):
        junctors: list[SubLabel] = get_junctors_between(labels=labels, first=event_labels[index], second=event_labels[index+1])
        junctor: bool = None
        if len(junctors) == 1:
            junctor = 'AND' if junctors[0].name == 'Conjunction' else 'OR'
        event_labels[index].set_successor(successor=event_labels[index+1], junctor=junctor)
        

def get_junctors_between(labels: list[Label], first: EventLabel, second: EventLabel) -> list[SubLabel]:
    """Retrieve all junctors between the first and second event label
    
    parameters:
        labels -- list of all labels
        first -- event label from whose end point the search begins
        second -- event label where the search ends
        
    returns: all conjunctions and disjunctions between the two event labels"""

    junctors: list[SubLabel] = [label for label in labels if (label.begin >= first.end and label.end <= second.begin and label.name in ['Conjunction', 'Disjunction'])]

    return junctors

def advance_cursor(token: str) -> int:
    """Calculate the amount of characters the cursor needs to jump to the next token. The calculation takes into account that certain characters cause the token splitter to introduce more whitespaces than others.

    parameters:
        token -- current token

    returns: number of characters until the next token
    """
    if token.startswith('##'):
        return 1
    elif token == ',':
        return len(token)
    elif token.startswith("'"):
        return len(token)
    else:
        return len(token) + 1