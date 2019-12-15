import intcode
import sys
import numpy as np
import itertools

fn = 'day15.txt'

def draw_grid(grid):
    xs = {int(c.real) for c in grid}
    ys = {int(c.imag) for c in grid}
    
    for y in range(max(ys) + 5, min(ys) - 6, -1):
        for x in range(min(xs) - 5, max(xs) + 6):
            c = grid.get(complex(x, y), ' ')
            sys.stdout.write(c)
        sys.stdout.write('\n')

def check_node(node, grid):
    around = [node + 1, node - 1, node + 1j, node - 1j]
    return all(a in grid for a in around)

thread, inputs, outputs, needs_input = intcode.standalone_processer(fn)

current_position = 0j
last_position = None

current_direction = 1j
grid = {current_position: 'D'}

inp_to_direction = {
    1: 1j,
    2: -1j,
    3: -1,
    4: 1,
}

direction_to_inp = {d: i for i, d in inp_to_direction.items()}
fewest_steps = {}
incomplete_nodes = set([0j])

mode = 'find first wall'
oxygen_at = None

step = 0
while thread.is_alive():
    step += 1
    needs_input.wait()
    needs_input.clear()
    
    if mode == 'find first wall':
        if grid.get(current_position + (current_direction), None) != '#':
            # go foward
            pass
        else:
            mode = 'found it'
            # turn right
            current_direction *= -1j
    else:
        # if no wall to left, move left
        if grid.get(current_position + (current_direction * 1j), None) != '#':
            # unless that is where you came from
            if last_position != current_position + (current_direction * 1j):
                # turn left
                current_direction *= 1j
            else:
                current_direction *= -1j
        elif grid.get(current_position + current_direction, None) != '#':
            # go straight
            pass
        elif grid.get(current_position + (current_direction * -1j), None) != '#':
            # turn right
            current_direction *= -1j
        else:
            # turn around
            current_direction *= -1

    inp = direction_to_inp[current_direction]

    inputs.put(inp)
    
    output = outputs.get()
    
    if output == 0:
        wall_at = current_position + inp_to_direction[inp]
        grid[wall_at] = '#'

    else:
        last_position = current_position
        previous_fewest = fewest_steps.get(current_position, 0)
        grid[current_position] = '.'
        grid[0j] = 's'
        current_position = current_position + inp_to_direction[inp]
        fewest_steps[current_position] = min(fewest_steps.get(current_position, np.inf), previous_fewest + 1)
        grid[current_position] = 'D'

        if not check_node(current_position, grid):
            incomplete_nodes.add(current_position)

        if output == 2:
            oxygen_at = current_position
            print(f'oxygen at {oxygen_at}, fewest steps = {fewest_steps[oxygen_at]}')

    if current_position in incomplete_nodes:
        if check_node(current_position, grid):
            incomplete_nodes.remove(current_position)
    
    if len(incomplete_nodes) == 0:
        inputs.put('KILL')
        break

for k, v in grid.items():
    if v == 'D' or v == 's':
        grid[k] = '.'

grid[oxygen_at] = 'O'

def next_to_oxygen(p, grid):
    around = [p + 1, p - 1, p + 1j, p - 1j]
    return any(grid[a] == 'O' for a in around)

for t in itertools.count():
    unfilled = {k for k, v in grid.items() if v == '.'}
    to_fill = {k for k in unfilled if next_to_oxygen(k, grid)}
    for k in to_fill:
        grid[k] = 'O'
    if len(unfilled) == 0:
        print(f'oxygen filled at {t}')
        break