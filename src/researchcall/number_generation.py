"""
Telephone number generation for survey sampling frames.
Implements the Gabler-Haeder method.
"""

import csv
import random
import re
import argparse
import sys

def read_block_file(path):
    """
    Read a CSV of number blocks.
    
    The CSV must have a header 'prefix,block_start,block_size'.
    Validates that:
    - prefix starts with '+'
    - block_size is one of 10, 100, 1000, 10000
    - block_start is numeric
    """
    blocks = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prefix = row['prefix']
            block_start = row['block_start']
            block_size_str = row['block_size']
            
            if not prefix.startswith('+'):
                raise ValueError(f"Invalid prefix: {prefix}. Must start with '+'.")
            
            if not block_start.isdigit():
                raise ValueError(f"Invalid block_start: {block_start}. Must be numeric.")
            
            try:
                block_size = int(block_size_str)
            except ValueError:
                raise ValueError(f"Invalid block_size: {block_size_str}. Must be an integer.")
                
            if block_size not in (10, 100, 1000, 10000):
                raise ValueError(f"Invalid block_size: {block_size}. Must be one of (10, 100, 1000, 10000).")
                
            blocks.append({
                'prefix': prefix,
                'block_start': block_start,
                'block_size': block_size
            })
    return blocks

def generate_frame(blocks, count, seed):
    """
    Generate a sampling frame of telephone numbers deterministically using a seed.
    Draws blocks uniformly and then randomizes an offset within the block.
    """
    rng = random.Random(seed)
    
    total_capacity = sum(b['block_size'] for b in blocks)
    if count > total_capacity:
        raise ValueError(f"Requested count {count} is larger than available numbers {total_capacity}.")
        
    e164_regex = re.compile(r'^\+[1-9]\d{6,14}$')
    
    generated_numbers_set = set()
    generated_numbers_list = []
    
    while len(generated_numbers_list) < count:
        block = rng.choice(blocks)
        offset = rng.randrange(block['block_size'])
        
        block_start_int = int(block['block_start'])
        number_int = block_start_int + offset
        
        number_str = f"{block['prefix']}{str(number_int).zfill(len(block['block_start']))}"
        
        if not e164_regex.match(number_str):
            raise ValueError(f"Generated number {number_str} is not a valid E.164 number.")
            
        if number_str not in generated_numbers_set:
            generated_numbers_set.add(number_str)
            generated_numbers_list.append(number_str)
            
    return generated_numbers_list

def write_frame_csv(numbers, path):
    """
    Write generated numbers to a CSV file.
    The file will have columns 'external_ref' and 'phone'.
    """
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['external_ref', 'phone'])
        for i, number in enumerate(numbers, start=1):
            writer.writerow([f"gen-{i:06d}", number])

def main():
    parser = argparse.ArgumentParser(description="Generate telephone numbers for survey sampling frames.")
    parser.add_argument("--blocks", required=True, help="Path to the blocks CSV file.")
    parser.add_argument("--count", required=True, type=int, help="Number of phone numbers to generate.")
    parser.add_argument("--seed", required=True, type=int, help="Random seed for deterministic generation.")
    parser.add_argument("--out", required=True, help="Path to the output CSV file.")
    
    args = parser.parse_args()
    
    try:
        blocks = read_block_file(args.blocks)
        numbers = generate_frame(blocks, args.count, args.seed)
        write_frame_csv(numbers, args.out)
        print(f"Successfully generated {args.count} numbers and saved to {args.out}.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
