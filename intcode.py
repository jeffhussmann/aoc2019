from collections import defaultdict
from queue import Queue
from threading import Thread, Event
from enum import Enum
from pathlib import Path

class Opcode(Enum):
    ADD = 1
    MULTIPLY = 2
    INPUT = 3
    OUTPUT = 4
    JUMP_IF_TRUE = 5
    JUMP_IF_FALSE = 6
    LESS_THAN = 7
    EQUALS = 8
    ADJUST_RELATIVE_BASE = 9
    BREAK = 99

opcode_to_num_params = {
    Opcode.ADD: 3,
    Opcode.MULTIPLY: 3,
    Opcode.INPUT: 1,
    Opcode.OUTPUT: 1,
    Opcode.JUMP_IF_TRUE: 2,
    Opcode.JUMP_IF_FALSE: 2,
    Opcode.LESS_THAN: 3,
    Opcode.EQUALS: 3,
    Opcode.ADJUST_RELATIVE_BASE: 1,
    Opcode.BREAK: 0,
}

def parse_opcode(pc, instructions, relative_base):
    full_opcode = instructions[pc]

    opcode = Opcode(full_opcode % 100)

    num_params = opcode_to_num_params[opcode]

    modes = [(full_opcode // 10**(2 + i)) % 10 for i in range(num_params)]

    addresses = list(range(pc + 1, pc + 1 + num_params))

    for i, m in enumerate(modes):
        if m == 0:
            addresses[i] = instructions[addresses[i]]
        elif m == 2:
            addresses[i] = instructions[addresses[i]] + relative_base

    return opcode, addresses

class FakeQueue:
    def __init__(self, vals):
        self.vals = vals
        
    def get(self):
        return self.vals.pop(0)
    
    def put(self, v):
        self.vals.append(v)
        
    def __str__(self):
        return str(self.vals)
    
    def empty(self):
        return len(self.vals) == 0

def make_fake_queue(queue):
    if queue is None:
        queue = []
        
    if isinstance(queue, list):
        queue = FakeQueue(queue)
        
    return queue
    
class Program:
    def __init__(self,
                 instructions_source,
                 input_queue=None,
                 output_queue=None,
                 needs_input=None,
                 memory_overrides=None,
                 pc=0,
                 relative_base=0,
                ):
        self.instructions = defaultdict(int)
        
        if isinstance(instructions_source, (str, Path)):
            with open(instructions_source) as fh:
                for i, s in enumerate(fh.read().strip().split(',')):
                    self.instructions[i] = int(s)
        elif isinstance(instructions_source, dict):
            self.instructions.update(instructions_source)
        elif isinstance(instructions_source, (list)):
            for i, s in enumerate(instructions_source):
                self.instructions[i] = s
            
        if memory_overrides is not None:
            for i, v in memory_overrides.items():
                self.instructions[i] = v
            
        self.pc = pc
        self.relative_base = relative_base
            
        self.input_queue = make_fake_queue(input_queue)
        self.output_queue = make_fake_queue(output_queue)
        self.needs_input = needs_input
        
    def clone(self):
        return Program(self.instructions.copy(), pc=self.pc, relative_base=self.relative_base)
        
    def run(self, until_input_needed=False):
        while True:
            opcode, args = parse_opcode(self.pc, self.instructions, self.relative_base)

            advance = True

            if opcode == Opcode.ADD:      
                self.instructions[args[2]] = self.instructions[args[0]] + self.instructions[args[1]]

            elif opcode == Opcode.MULTIPLY:                   
                self.instructions[args[2]] = self.instructions[args[0]] * self.instructions[args[1]]

            elif opcode == Opcode.INPUT:
                if until_input_needed and self.input_queue.empty():
                    return
                
                if self.needs_input is not None:
                    self.needs_input.set()
                
                value = self.input_queue.get()
                
                if value == 'KILL':
                    return
                
                self.instructions[args[0]] = value

            elif opcode == Opcode.OUTPUT:
                self.output_queue.put(self.instructions[args[0]])

            elif opcode == Opcode.JUMP_IF_TRUE:               
                if self.instructions[args[0]] != 0:
                    self.pc = self.instructions[args[1]]
                    advance = False

            elif opcode == Opcode.JUMP_IF_FALSE:        
                if self.instructions[args[0]] == 0:
                    self.pc = self.instructions[args[1]]
                    advance = False

            elif opcode == Opcode.LESS_THAN:
                if self.instructions[args[0]] < self.instructions[args[1]]:
                    self.instructions[args[2]] = 1
                else:
                    self.instructions[args[2]] = 0

            elif opcode == Opcode.EQUALS:
                if self.instructions[args[0]] == self.instructions[args[1]]:
                    self.instructions[args[2]] = 1
                else:
                    self.instructions[args[2]] = 0
                    
            elif opcode == Opcode.ADJUST_RELATIVE_BASE:
                self.relative_base += self.instructions[args[0]]

            elif opcode == Opcode.BREAK:
                if self.needs_input is not None:
                    self.needs_input.set()
                return

            if advance:
                self.pc += len(args) + 1

    def convert_inputs_to_outputs(self, inputs):
        for inp in inputs:
            self.input_queue.put(inp)

        self.run(until_input_needed=True)

        outputs = []
        while not self.output_queue.empty():
            outputs.append(self.output_queue.get())

        return outputs

def run_program(fn, input_queue, output_queue, needs_input, memory_overrides):
    program = Program(fn, input_queue, output_queue, needs_input, memory_overrides)
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
        args = (fn, input_queues[name], output_queues[name])
        threads[name] = Thread(target=run_program, args=args)
        threads[name].start()

    return threads, input_queues, output_queues

def standalone_processer(fn, memory_overrides=None):
    inputs = Queue()
    outputs = Queue()
    needs_input = Event()
    done = Event()
    thread = Thread(target=run_program, args=(fn, inputs, outputs, needs_input, memory_overrides))
    thread.start()
    return thread, inputs, outputs, needs_input
