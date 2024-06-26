import pandas as pd

df = pd.read_csv('question_answer.csv')
df.head()

id_answer = df.set_index('id')['answer'].to_dict()

from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

connections.connect(host='127.0.0.1', port='27017')

def create_milvus_collection(collection_name, dim):
    if utility.has_collection(collection_name):
        utility.drop_collection(collection_name)
    
    fields = [
    FieldSchema(name='id', dtype=DataType.VARCHAR, descrition='ids', max_length=500, is_primary=True, auto_id=False),
    FieldSchema(name='embedding', dtype=DataType.FLOAT_VECTOR, descrition='embedding vectors', dim=dim)
    ]
    schema = CollectionSchema(fields=fields, description='reverse image search')
    collection = Collection(name=collection_name, schema=schema)

    # create IVF_FLAT index for collection.
    index_params = {
        'metric_type':'L2',
        'index_type':"IVF_FLAT",
        'params':{"nlist":2048}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    return collection

collection = create_milvus_collection('question_answer', 768)


from towhee import pipe, ops
import numpy as np
from towhee.datacollection import DataCollection

insert_pipe = (
    pipe.input('id', 'question', 'answer')
        .map('question', 'vec', ops.text_embedding.dpr(model_name='facebook/dpr-ctx_encoder-single-nq-base'))
        .map('vec', 'vec', lambda x: x / np.linalg.norm(x, axis=0))
        .map(('id', 'vec'), 'insert_status', ops.ann_insert.milvus_client(host='127.0.0.1', port='27017', collection_name='question_answer'))
        .output()
)

import csv
with open('question_answer.csv', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        insert_pipe(*row)

collection.load()
ans_pipe = (
    pipe.input('question')
        .map('question', 'vec', ops.text_embedding.dpr(model_name="facebook/dpr-ctx_encoder-single-nq-base"))
        .map('vec', 'vec', lambda x: x / np.linalg.norm(x, axis=0))
        .map('vec', 'res', ops.ann_search.milvus_client(host='127.0.0.1', port='27017', collection_name='question_answer', limit=1))
        .map('res', 'answer', lambda x: [id_answer[int(i[0])] for i in x])
        .output('question', 'answer')
)


ans = ans_pipe('Is  Disability  Insurance  Required  By  Law?')
ans = DataCollection(ans)
ans.show()


import towhee
def chat(message, history):
    history = history or []
    ans_pipe = (
        pipe.input('question')
            .map('question', 'vec', ops.text_embedding.dpr(model_name="facebook/dpr-ctx_encoder-single-nq-base"))
            .map('vec', 'vec', lambda x: x / np.linalg.norm(x, axis=0))
            .map('vec', 'res', ops.ann_search.milvus_client(host='127.0.0.1', port='27017', collection_name='question_answer', limit=1))
            .map('res', 'answer', lambda x: [id_answer[int(i[0])] for i in x])
            .output('question', 'answer')
    )

    response = ans_pipe(message).get()[1][0]
    history.append((message, response))
    return history, history

import gradio

collection.load()
chatbot = gradio.Chatbot()
interface = gradio.Interface(
    chat,
    ["text", "state"],
    [chatbot, "state"],
    allow_flagging="never",
)
interface.launch(inline=True, share=True)
