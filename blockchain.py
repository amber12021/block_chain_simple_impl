# {
#     "index":0,
#     "timestamp":"",
#     "transactions":[
#         {
#             "sender":"", 发送者
#             "recipient":"", 接受者
#             "amount": 5, 金额
#         }
#     ],
#     "peoof":"", 区块链的工作证明
#     "precious_hash":"",
# }
import hashlib
import json
from time import time, sleep
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request


class Blockchain:
    # 初始化区块链
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        # 创世纪区块是不用计算的，因为它没有任何内容，proof 工作量是不需要任何计算的随意写一个数，上一个区块hash直接写一个1
        self.new_block(proof=100, previous_hash=1)

    # 注册的节点
    def register_node(self, address: str):
        parse_url = urlparse(address)
        self.nodes.add(parse_url.netloc)

    # 解决冲突
    def reslove_conflicts(self) -> bool:
        neighbours = self.nodes

        max_length = len(self.chain)
        new_chain = None

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                # 如果nodes里面的chain大于当前链条，并且是合法的chain，
                if length > max_length and self.valid_chain(chain):
                    # 更改chain length
                    max_length = length
                    # 修改新的chain
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

    # 新建一个区块
    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            # -1表示数组里面的最后一个 self.hash(self.chain[-1])
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }
        # 当前交易清空
        self.current_transactions = []
        # 在区块链上加入该块
        self.chain.append(block)
        return block

    # 新建一笔交易 返回当前索引，也就是上一个索引+1
    def new_transaction(self, sender, recipient, amount) -> int:
        self.current_transactions.append(
            {
                'sender': sender,
                'recipient': recipient,
                'amount': amount
            }
        )
        return self.last_block['index'] + 1

    # 对块进行hash
    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        # 返回一个hash的摘要
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    # 工作量证明
    def proof_of_work(self, last_proof: int) -> int:
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

            # print(proof)
        return proof

    def valid_proof(self, last_proof: int, proof: int) -> bool:
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        # sleep(1)
        print(guess_hash)
        # if guess_hash[0:4] == "0000":
        #     return True
        # else:
        #     return False
        return guess_hash[0:4] == "0000"

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]

            # hash不匹配
            if block['previous_hash'] != self.hash(last_block):
                return False
            # 满足0000开头
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            last_block = block
            current_index += 1
        return True


# 使用uuid生成一个随机uuid
node_identifier = str(uuid4()).replace('-', '')

# 测试工作证明
# testPow = Blockchain()
# testPow.proof_of_work(100)

# 启动一个server
app = Flask(__name__)
blockchain = Blockchain()


@app.route('/index', methods=['GET'])
def index():
    return "Hello BlockChain"


@app.route('/transaction/new', methods=['POST'])
def newTransactions():
    values = request.get_json()
    required = ["sender", "recipient", "amount"]
    if values is None:
        return "Missing values", 400

    # 进行验证 request 包含required数据
    if not all(k in values for k in required):
        return "Missing values", 400
    blockchain.new_transaction(values['sender'],
                               values['recipient'],
                               values['amount'])
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


# n. 矿，
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction(sender="0",
                               recipient=node_identifier,
                               amount=1)

    block = blockchain.new_block(proof, None)

    response = {
        "message": "New Block Forged",
        "index": block['index'],
        "transactions": block['transactions'],
        'proof': block['proof'],
        "previous_hash": block['previous_hash']
    }

    return jsonify(response), 200


# 返回所有区块
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }

    return jsonify(response), 200


# 实现注册节点
# {"nodes": ["http://127.0.0.1:5100"]}
@app.route('/nodes/register', methods=['POST'])
def nodes_register():
    values = request.get_json()
    nodes = values.get("nodes")

    if nodes is None:
        return "Error: please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        "message": "New nodes have benn added",
        "total_nodes": list(blockchain.nodes)
    }

    return jsonify(response), 201


# 共识机制
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.reslove_conflicts()

    # 取代
    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='prot to listen on')
    args = parser.parse_args()
    port = args.port
    # -p --port
    app.run(host='0.0.0.0', port=port)
