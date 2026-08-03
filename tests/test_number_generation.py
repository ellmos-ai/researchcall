"""
Tests for telephone number generation module.
"""

import unittest
import os
import tempfile
import csv
from researchcall.number_generation import read_block_file, generate_frame, write_frame_csv

class TestNumberGeneration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.blocks_file = os.path.join(self.temp_dir.name, "blocks.csv")
        self.out_file = os.path.join(self.temp_dir.name, "out.csv")
        
        with open(self.blocks_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['prefix', 'block_start', 'block_size'])
            writer.writerow(['+442079460', '000', '10'])
            writer.writerow(['+441632960', '000', '100'])
            writer.writerow(['+443069990', '000', '1000'])
            
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_determinism_same_seed(self):
        blocks = read_block_file(self.blocks_file)
        frame1 = generate_frame(blocks, 50, seed=42)
        frame2 = generate_frame(blocks, 50, seed=42)
        self.assertEqual(frame1, frame2)

    def test_determinism_different_seed(self):
        blocks = read_block_file(self.blocks_file)
        frame1 = generate_frame(blocks, 50, seed=42)
        frame2 = generate_frame(blocks, 50, seed=99)
        self.assertNotEqual(frame1, frame2)

    def test_no_duplicates(self):
        blocks = read_block_file(self.blocks_file)
        frame = generate_frame(blocks, 100, seed=42)
        self.assertEqual(len(frame), len(set(frame)))

    def test_e164_validity(self):
        blocks = read_block_file(self.blocks_file)
        frame = generate_frame(blocks, 50, seed=42)
        import re
        e164_regex = re.compile(r'^\+[1-9]\d{6,14}$')
        for number in frame:
            self.assertTrue(e164_regex.match(number))

    def test_block_file_validation_errors(self):
        bad_blocks_file = os.path.join(self.temp_dir.name, "bad_blocks.csv")
        with open(bad_blocks_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['prefix', 'block_start', 'block_size'])
            writer.writerow(['030', '1234560', '10']) # bad prefix
        with self.assertRaises(ValueError):
            read_block_file(bad_blocks_file)
            
        with open(bad_blocks_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['prefix', 'block_start', 'block_size'])
            writer.writerow(['+442079460', '000', '50']) # bad block_size
        with self.assertRaises(ValueError):
            read_block_file(bad_blocks_file)

    def test_csv_round_trip_readable(self):
        blocks = read_block_file(self.blocks_file)
        frame = generate_frame(blocks, 10, seed=42)
        write_frame_csv(frame, self.out_file)
        
        with open(self.out_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        self.assertEqual(len(rows), 10)
        self.assertIn('external_ref', rows[0])
        self.assertIn('phone', rows[0])
        self.assertEqual(rows[0]['phone'], frame[0])

    def test_count_larger_than_available_raises(self):
        blocks = read_block_file(self.blocks_file)
        # Total capacity is 10 + 100 + 1000 = 1110
        with self.assertRaises(ValueError):
            generate_frame(blocks, 1200, seed=42)

    def test_external_ref_numbering_stable(self):
        blocks = read_block_file(self.blocks_file)
        frame = generate_frame(blocks, 5, seed=42)
        write_frame_csv(frame, self.out_file)
        
        with open(self.out_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        self.assertEqual(rows[0]['external_ref'], "gen-000001")
        self.assertEqual(rows[4]['external_ref'], "gen-000005")

if __name__ == '__main__':
    unittest.main()
