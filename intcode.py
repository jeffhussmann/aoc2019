from collections import defaultdict
from queue import Queue
from threading import Thread, Event

opcodes = {
        1: (3, 'ADD'),
        2: (3, 'MULT'),
        3: (1, 'INPUT'),
        4: (1, 'OUTPUT'),
        5: (2, 'JUMP IF TRUE'),
        6: (2, 'JUMP IF TRUE'),
        7: (3, 'LESS THAN'),
        8: (3, 'EQUALS'),
        9: (1, 'ADJUST RELATIVE BASE'),
        99: (0, 'BREAK'),
    }

def parse_opcode(pc, instructions, relative_base):
    full_opcode = instructions[pc]

    opcode = full_opcode % 100

    num_params, name = opcodes[opcode]

    modes = [(full_opcode // 10**(2 + i)) % 10 for i in range(num_params)]

    addresses = list(range(pc + 1, pc + 1 + num_params))

    for i, m in enumerate(modes):
        if m == 0:
            addresses[i] = instructions[addresses[i]]
        elif m == 2:
            addresses[i] = instructions[addresses[i]] + relative_base

    return opcode, addresses

class FakeQueue():
    def __init__(self, l):
        self.l = l
        
    def get(self):
        return self.l.pop(0)
    
    def put(self, v):
        self.l.append(v)
        
    def __str__(self):
        return str(self.l)

def make_fake_queue(queue):
    if queue is None:
        queue = []
        
    if isinstance(queue, list):
        queue = FakeQueue(queue)
        
    return queue
    
class Program():
    def __init__(self, name, fn, input_queue=None, output_queue=None, needs_input=None, memory_overrides=None):
        self.name = name
        
        self.instructions = defaultdict(int)
        for i, s in enumerate(open(fn).read().strip().split(',')):
            self.instructions[i] = int(s)
            
        if memory_overrides is not None:
            for i, v in memory_overrides.items():
                self.instructions[i] = v
            
        self.pc = 0
        self.relative_base = 0
            
        self.input_queue = make_fake_queue(input_queue)
        self.output_queue = make_fake_queue(output_queue)
        self.needs_input = needs_input

    def run(self):
        while True:
            opcode, args = parse_opcode(self.pc, self.instructions, self.relative_base)

            advance = True

            if opcode == 1:      
                self.instructions[args[2]] = self.instructions[args[0]] + self.instructions[args[1]]

            elif opcode == 2:                   
                self.instructions[args[2]] = self.instructions[args[0]] * self.instructions[args[1]]

            elif opcode == 3:
                self.needs_input.set()
                value = self.input_queue.get()
                if value == 'KILL':
                    break
                self.instructions[args[0]] = value

            elif opcode == 4:
                self.output_queue.put(self.instructions[args[0]])

            elif opcode == 5:               
                if self.instructions[args[0]] != 0:
                    self.pc = self.instructions[args[1]]
                    advance = False

            elif opcode == 6:        
                if self.instructions[args[0]] == 0:
                    self.pc = self.instructions[args[1]]
                    advance = False

            elif opcode == 7:
                if self.instructions[args[0]] < self.instructions[args[1]]:
                    self.instructions[args[2]] = 1
                else:
                    self.instructions[args[2]] = 0

            elif opcode == 8:
                if self.instructions[args[0]] == self.instructions[args[1]]:
                    self.instructions[args[2]] = 1
                else:
                    self.instructions[args[2]] = 0
                    
            elif opcode == 9:
                self.relative_base += self.instructions[args[0]]

            elif opcode == 99:
                self.needs_input.set()
                break

            if advance:
                self.pc += len(args) + 1

def run_program(name, fn, input_queue, output_queue, needs_input, memory_overrides):
    program = Program(name, fn, input_queue, output_queue, needs_input, memory_overrides)
    program.run()
    
def connect_processors(fn, names, connections):
    input_queues = {}
    output_queues = {}

    for output_from, input_to in connections:
        queue = Queue()
        if input_to is not None:
            input_queues[input_to] = queue
        if output_from is not None:
            output_queues[output_from] = queue

    threads = {}
    
    for name in names:
        args = (name, fn, input_queues[name], output_queues[name])
        threads[name] = Thread(target=run_program, args=args)
        threads[name].start()

    return threads, input_queues, output_queues

def standalone_processer(fn, memory_overrides=None):
    inputs = Queue()
    outputs = Queue()
    needs_input = Event()
    done = Event()
    thread = Thread(target=run_program, args=('', fn, inputs, outputs, needs_input, memory_overrides))
    thread.start()
    return thread, inputs, outputs, needs_input