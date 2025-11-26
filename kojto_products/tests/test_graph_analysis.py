# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install', 'kojto_products')
class TestGraphAnalysis(TransactionCase):
    """Test suite for top-down and bottom-up graph analysis"""

    @classmethod
    def setUpClass(cls):
        super(TestGraphAnalysis, cls).setUpClass()
        print("\n" + "="*80)
        print("Setting up Graph Analysis test environment...")
        print("="*80)

        # Create test units
        cls.unit_kg = cls.env['kojto.base.units'].create({
            'name': 'kg',
            'unit_type': 'weight',
            'conversion_factor': 1.0,
        })
        cls.unit_pcs = cls.env['kojto.base.units'].create({
            'name': 'pcs',
            'unit_type': 'quantity',
            'conversion_factor': 1.0,
        })
        print(f"Created test units: {cls.unit_kg.name}, {cls.unit_pcs.name}")

        # Use or create test subcode with full hierarchy
        cls.subcode_test = cls.env['kojto.commission.subcodes'].search([('active', '=', True)], limit=1)
        if not cls.subcode_test:
            # Create full hierarchy: maincode -> code -> subcode
            maincode = cls.env['kojto.commission.main.codes'].create({
                'maincode': '99',
                'name': 'Test Main Code',
                'description': 'Test Main Code for Graph Analysis Tests',
            })
            code = cls.env['kojto.commission.codes'].create({
                'code': '99',
                'maincode_id': maincode.id,
                'description': 'Test Code for Graph Analysis Tests',
            })
            cls.subcode_test = cls.env['kojto.commission.subcodes'].create({
                'subcode': '999',
                'code_id': code.id,
                'description': 'Test Subcode for Graph Analysis Tests',
            })
            cls.created_test_data = True
            print(f"Created test subcode hierarchy: {cls.subcode_test.name}")
        else:
            cls.created_test_data = False
            print(f"Using existing subcode: {cls.subcode_test.name}")

        # Create test components for a simple graph structure:
        # Assembly (Root)
        #   ├── SubAssembly1 (qty: 2)
        #   │   ├── Part1 (qty: 3)
        #   │   └── Part2 (qty: 2)
        #   └── SubAssembly2 (qty: 1)
        #       └── Part1 (qty: 4)

        cls.component_assembly = cls.env['kojto.product.component'].create({
            'name': 'Assembly',
            'unit_id': cls.unit_pcs.id,
            'subcode_id': cls.subcode_test.id,
        })
        cls.component_subassembly1 = cls.env['kojto.product.component'].create({
            'name': 'SubAssembly1',
            'unit_id': cls.unit_pcs.id,
            'subcode_id': cls.subcode_test.id,
        })
        cls.component_subassembly2 = cls.env['kojto.product.component'].create({
            'name': 'SubAssembly2',
            'unit_id': cls.unit_pcs.id,
            'subcode_id': cls.subcode_test.id,
        })
        cls.component_part1 = cls.env['kojto.product.component'].create({
            'name': 'Part1',
            'unit_id': cls.unit_pcs.id,
            'subcode_id': cls.subcode_test.id,
        })
        cls.component_part2 = cls.env['kojto.product.component'].create({
            'name': 'Part2',
            'unit_id': cls.unit_pcs.id,
            'subcode_id': cls.subcode_test.id,
        })
        print(f"Created test components: Assembly, SubAssembly1, SubAssembly2, Part1, Part2")

        # Use the auto-created revisions (components automatically create initial revision)
        # Update their attributes for testing
        cls.rev_assembly = cls.component_assembly.latest_revision_id
        cls.rev_assembly.write({
            'weight_attribute': 50.0,
            'length_attribute': 100.0,
            'area_attribute': 5.0,
            'volume_attribute': 2.0,
            'price_attribute': 500.0,
            'time_attribute': 60.0,
            'other_attribute': 1.0,
        })

        cls.rev_subassembly1 = cls.component_subassembly1.latest_revision_id
        cls.rev_subassembly1.write({
            'weight_attribute': 10.0,
            'length_attribute': 30.0,
            'area_attribute': 2.0,
            'volume_attribute': 0.5,
            'price_attribute': 100.0,
            'time_attribute': 15.0,
            'other_attribute': 0.2,
        })

        cls.rev_subassembly2 = cls.component_subassembly2.latest_revision_id
        cls.rev_subassembly2.write({
            'weight_attribute': 15.0,
            'length_attribute': 40.0,
            'area_attribute': 2.5,
            'volume_attribute': 0.8,
            'price_attribute': 150.0,
            'time_attribute': 20.0,
            'other_attribute': 0.3,
        })

        cls.rev_part1 = cls.component_part1.latest_revision_id
        cls.rev_part1.write({
            'weight_attribute': 2.0,
            'length_attribute': 10.0,
            'area_attribute': 0.5,
            'volume_attribute': 0.1,
            'price_attribute': 20.0,
            'time_attribute': 5.0,
            'other_attribute': 0.05,
        })

        cls.rev_part2 = cls.component_part2.latest_revision_id
        cls.rev_part2.write({
            'weight_attribute': 3.0,
            'length_attribute': 15.0,
            'area_attribute': 0.8,
            'volume_attribute': 0.2,
            'price_attribute': 30.0,
            'time_attribute': 8.0,
            'other_attribute': 0.08,
        })
        print(f"Updated auto-created revisions with test attributes")

        # Create links to form the graph structure
        # Assembly -> SubAssembly1 (qty: 2)
        cls.link1 = cls.env['kojto.product.component.revision.link'].create({
            'source_revision_id': cls.rev_assembly.id,
            'target_subcode_id': cls.subcode_test.id,
            'target_component_id': cls.component_subassembly1.id,
            'quantity': 2.0,
        })

        # Assembly -> SubAssembly2 (qty: 1)
        cls.link2 = cls.env['kojto.product.component.revision.link'].create({
            'source_revision_id': cls.rev_assembly.id,
            'target_subcode_id': cls.subcode_test.id,
            'target_component_id': cls.component_subassembly2.id,
            'quantity': 1.0,
        })

        # SubAssembly1 -> Part1 (qty: 3)
        cls.link3 = cls.env['kojto.product.component.revision.link'].create({
            'source_revision_id': cls.rev_subassembly1.id,
            'target_subcode_id': cls.subcode_test.id,
            'target_component_id': cls.component_part1.id,
            'quantity': 3.0,
        })

        # SubAssembly1 -> Part2 (qty: 2)
        cls.link4 = cls.env['kojto.product.component.revision.link'].create({
            'source_revision_id': cls.rev_subassembly1.id,
            'target_subcode_id': cls.subcode_test.id,
            'target_component_id': cls.component_part2.id,
            'quantity': 2.0,
        })

        # SubAssembly2 -> Part1 (qty: 4)
        cls.link5 = cls.env['kojto.product.component.revision.link'].create({
            'source_revision_id': cls.rev_subassembly2.id,
            'target_subcode_id': cls.subcode_test.id,
            'target_component_id': cls.component_part1.id,
            'quantity': 4.0,
        })
        print(f"Created test links forming graph structure")
        print("Setup completed successfully!")
        print("="*80 + "\n")

    @classmethod
    def tearDownClass(cls):
        print("\n" + "="*80)
        print("Cleaning up Graph Analysis test environment...")
        print("="*80)
        # Links are automatically deleted due to cascade
        # Revisions are automatically deleted due to cascade
        if hasattr(cls, 'component_assembly'):
            cls.component_assembly.unlink()
        if hasattr(cls, 'component_subassembly1'):
            cls.component_subassembly1.unlink()
        if hasattr(cls, 'component_subassembly2'):
            cls.component_subassembly2.unlink()
        if hasattr(cls, 'component_part1'):
            cls.component_part1.unlink()
        if hasattr(cls, 'component_part2'):
            cls.component_part2.unlink()
        if hasattr(cls, 'unit_kg'):
            cls.unit_kg.unlink()
        if hasattr(cls, 'unit_pcs'):
            cls.unit_pcs.unlink()
        # Only delete test subcode if we created it (not if we used existing)
        if hasattr(cls, 'created_test_data') and cls.created_test_data:
            if hasattr(cls, 'subcode_test') and cls.subcode_test.exists():
                # Delete will cascade to code and maincode due to ondelete="cascade"
                maincode = cls.subcode_test.maincode_id
                code = cls.subcode_test.code_id
                cls.subcode_test.unlink()
                if code.exists():
                    code.unlink()
                if maincode.exists():
                    maincode.unlink()
                print("Deleted test subcode hierarchy")
        print("Cleanup completed successfully!")
        print("="*80 + "\n")
        super(TestGraphAnalysis, cls).tearDownClass()

    def test_01_graph_resolution_tree_mode(self):
        """Test that resolve_graph in tree mode correctly builds the graph structure"""
        print("\n" + "-"*80)
        print("TEST 01: Graph Resolution (Tree Mode)")
        print("-"*80)

        from ..utils.kojto_products_graph_utils import resolve_graph

        visited, edges, aggregated_attributes, lock_status = resolve_graph(
            start_revision=self.rev_assembly,
            env=self.env,
            mode='tree'
        )

        print(f"Visited nodes: {len(visited)}")
        print(f"Edges found: {len(edges)}")
        print(f"Expected edges: 5")

        # Verify all nodes were visited
        self.assertEqual(len(visited), 5, "Should visit 5 nodes (Assembly, 2 SubAssemblies, 2 Parts)")
        self.assertIn(self.rev_assembly.id, visited)
        self.assertIn(self.rev_subassembly1.id, visited)
        self.assertIn(self.rev_subassembly2.id, visited)
        self.assertIn(self.rev_part1.id, visited)
        self.assertIn(self.rev_part2.id, visited)

        # Verify edges
        self.assertEqual(len(edges), 5, "Should have 5 edges")
        self.assertIn((self.rev_assembly.id, self.rev_subassembly1.id), edges)
        self.assertIn((self.rev_assembly.id, self.rev_subassembly2.id), edges)
        self.assertIn((self.rev_subassembly1.id, self.rev_part1.id), edges)
        self.assertIn((self.rev_subassembly1.id, self.rev_part2.id), edges)
        self.assertIn((self.rev_subassembly2.id, self.rev_part1.id), edges)

        # Verify aggregated attributes exist for all nodes
        self.assertEqual(len(aggregated_attributes), 5, "Should have attributes for all 5 nodes")
        for rev_id in visited:
            self.assertIn(rev_id, aggregated_attributes)
            attrs = aggregated_attributes[rev_id]
            self.assertIn('weight', attrs)
            self.assertIn('length', attrs)
            self.assertIn('area', attrs)
            self.assertIn('volume', attrs)
            self.assertIn('price', attrs)
            self.assertIn('time', attrs)
            self.assertIn('other', attrs)

        print("✓ Graph structure correctly resolved")
        print(f"✓ All {len(visited)} nodes visited")
        print(f"✓ All {len(edges)} edges found")
        print(f"✓ All {len(aggregated_attributes)} node attributes computed")
        print("-"*80)

    def test_02_top_down_aggregation(self):
        """Test that top-down aggregation correctly calculates cumulative attributes"""
        print("\n" + "-"*80)
        print("TEST 02: Top-Down Aggregation")
        print("-"*80)

        from ..utils.kojto_products_graph_utils import resolve_graph

        visited, edges, aggregated_attributes, lock_status = resolve_graph(
            start_revision=self.rev_assembly,
            env=self.env,
            mode='tree'
        )

        # Test leaf nodes (Part1, Part2) - should only have their own attributes
        part1_attrs = aggregated_attributes[self.rev_part1.id]
        part2_attrs = aggregated_attributes[self.rev_part2.id]

        print(f"\nPart1 attributes (leaf node):")
        print(f"  Weight: {part1_attrs['weight']} (expected: 2.0)")
        self.assertAlmostEqual(part1_attrs['weight'], 2.0, places=2)
        self.assertAlmostEqual(part1_attrs['price'], 20.0, places=2)
        print(f"  Price: {part1_attrs['price']} (expected: 20.0)")

        print(f"\nPart2 attributes (leaf node):")
        print(f"  Weight: {part2_attrs['weight']} (expected: 3.0)")
        self.assertAlmostEqual(part2_attrs['weight'], 3.0, places=2)
        self.assertAlmostEqual(part2_attrs['price'], 30.0, places=2)
        print(f"  Price: {part2_attrs['price']} (expected: 30.0)")

        # Test SubAssembly1 - should include its own attributes + (3 * Part1) + (2 * Part2)
        subasm1_attrs = aggregated_attributes[self.rev_subassembly1.id]
        expected_weight_subasm1 = 10.0 + (3 * 2.0) + (2 * 3.0)  # 10 + 6 + 6 = 22
        expected_price_subasm1 = 100.0 + (3 * 20.0) + (2 * 30.0)  # 100 + 60 + 60 = 220

        print(f"\nSubAssembly1 attributes (includes 3×Part1 + 2×Part2):")
        print(f"  Weight: {subasm1_attrs['weight']} (expected: {expected_weight_subasm1})")
        print(f"  Calculation: 10.0 (own) + 3×2.0 (Part1) + 2×3.0 (Part2) = {expected_weight_subasm1}")
        self.assertAlmostEqual(subasm1_attrs['weight'], expected_weight_subasm1, places=2)

        print(f"  Price: {subasm1_attrs['price']} (expected: {expected_price_subasm1})")
        print(f"  Calculation: 100.0 (own) + 3×20.0 (Part1) + 2×30.0 (Part2) = {expected_price_subasm1}")
        self.assertAlmostEqual(subasm1_attrs['price'], expected_price_subasm1, places=2)

        # Test SubAssembly2 - should include its own attributes + (4 * Part1)
        subasm2_attrs = aggregated_attributes[self.rev_subassembly2.id]
        expected_weight_subasm2 = 15.0 + (4 * 2.0)  # 15 + 8 = 23
        expected_price_subasm2 = 150.0 + (4 * 20.0)  # 150 + 80 = 230

        print(f"\nSubAssembly2 attributes (includes 4×Part1):")
        print(f"  Weight: {subasm2_attrs['weight']} (expected: {expected_weight_subasm2})")
        print(f"  Calculation: 15.0 (own) + 4×2.0 (Part1) = {expected_weight_subasm2}")
        self.assertAlmostEqual(subasm2_attrs['weight'], expected_weight_subasm2, places=2)

        print(f"  Price: {subasm2_attrs['price']} (expected: {expected_price_subasm2})")
        print(f"  Calculation: 150.0 (own) + 4×20.0 (Part1) = {expected_price_subasm2}")
        self.assertAlmostEqual(subasm2_attrs['price'], expected_price_subasm2, places=2)

        # Test Assembly (root) - should include all children
        # Assembly = own + (2 * SubAssembly1_total) + (1 * SubAssembly2_total)
        assembly_attrs = aggregated_attributes[self.rev_assembly.id]
        expected_weight_assembly = 50.0 + (2 * 22.0) + (1 * 23.0)  # 50 + 44 + 23 = 117
        expected_price_assembly = 500.0 + (2 * 220.0) + (1 * 230.0)  # 500 + 440 + 230 = 1170

        print(f"\nAssembly attributes (root - includes all):")
        print(f"  Weight: {assembly_attrs['weight']} (expected: {expected_weight_assembly})")
        print(f"  Calculation: 50.0 (own) + 2×22.0 (SubAssembly1) + 1×23.0 (SubAssembly2) = {expected_weight_assembly}")
        self.assertAlmostEqual(assembly_attrs['weight'], expected_weight_assembly, places=2)

        print(f"  Price: {assembly_attrs['price']} (expected: {expected_price_assembly})")
        print(f"  Calculation: 500.0 (own) + 2×220.0 (SubAssembly1) + 1×230.0 (SubAssembly2) = {expected_price_assembly}")
        self.assertAlmostEqual(assembly_attrs['price'], expected_price_assembly, places=2)

        print("\n✓ Top-down aggregation calculated correctly")
        print("✓ Leaf nodes have only their own attributes")
        print("✓ Parent nodes correctly aggregate child attributes with quantities")
        print("✓ Root node contains total aggregation of entire tree")
        print("-"*80)

    def test_03_bottom_up_path_collection(self):
        """Test that bottom-up path collection correctly identifies all paths"""
        print("\n" + "-"*80)
        print("TEST 03: Bottom-Up Path Collection")
        print("-"*80)

        from ..utils.kojto_products_graph_utils import resolve_graph
        from ..utils.kojto_products_collect_revision_paths import collect_revision_paths

        visited, edges, aggregated_attributes, lock_status = resolve_graph(
            start_revision=self.rev_assembly,
            env=self.env,
            mode='tree'
        )

        revision_map = {
            rev.id: rev for rev in self.env['kojto.product.component.revision'].browse(visited)
            if rev.exists()
        }

        paths, quantities, link_quantities = collect_revision_paths(
            self.rev_assembly.id, edges, revision_map, self.env
        )

        print(f"\nTotal revisions in paths: {len(paths)}")

        # Verify paths for Assembly (root) - should have 1 path (itself)
        assembly_paths = paths.get(self.rev_assembly.id, [])
        print(f"\nAssembly paths: {len(assembly_paths)}")
        self.assertEqual(len(assembly_paths), 1, "Assembly should have 1 path (itself)")

        # Verify paths for SubAssembly1 - should have 1 path through Assembly
        subasm1_paths = paths.get(self.rev_subassembly1.id, [])
        print(f"SubAssembly1 paths: {len(subasm1_paths)}")
        self.assertEqual(len(subasm1_paths), 1, "SubAssembly1 should have 1 path")

        # Verify paths for SubAssembly2 - should have 1 path through Assembly
        subasm2_paths = paths.get(self.rev_subassembly2.id, [])
        print(f"SubAssembly2 paths: {len(subasm2_paths)}")
        self.assertEqual(len(subasm2_paths), 1, "SubAssembly2 should have 1 path")

        # Verify paths for Part1 - should have 2 paths (through SubAssembly1 and SubAssembly2)
        part1_paths = paths.get(self.rev_part1.id, [])
        print(f"Part1 paths: {len(part1_paths)}")
        print(f"  Path 1: {' → '.join([f'{name}({qty})' for name, qty in part1_paths[0]])}")
        if len(part1_paths) > 1:
            print(f"  Path 2: {' → '.join([f'{name}({qty})' for name, qty in part1_paths[1]])}")
        self.assertEqual(len(part1_paths), 2, "Part1 should have 2 paths (through both SubAssemblies)")

        # Verify paths for Part2 - should have 1 path through SubAssembly1
        part2_paths = paths.get(self.rev_part2.id, [])
        print(f"Part2 paths: {len(part2_paths)}")
        self.assertEqual(len(part2_paths), 1, "Part2 should have 1 path")

        # Verify quantities - total quantity for Part1 should be (2*3) + (1*4) = 10
        part1_qty = quantities.get(self.rev_part1.id, 0.0)
        expected_part1_qty = (2 * 3) + (1 * 4)  # Through SubAssembly1: 2×3=6, Through SubAssembly2: 1×4=4
        print(f"\nPart1 total quantity: {part1_qty} (expected: {expected_part1_qty})")
        print(f"  Calculation: 2(Assembly→SubAssembly1) × 3(SubAssembly1→Part1) + 1(Assembly→SubAssembly2) × 4(SubAssembly2→Part1)")
        self.assertAlmostEqual(part1_qty, expected_part1_qty, places=2)

        # Verify quantities - total quantity for Part2 should be (2*2) = 4
        part2_qty = quantities.get(self.rev_part2.id, 0.0)
        expected_part2_qty = 2 * 2  # Through SubAssembly1: 2×2=4
        print(f"Part2 total quantity: {part2_qty} (expected: {expected_part2_qty})")
        print(f"  Calculation: 2(Assembly→SubAssembly1) × 2(SubAssembly1→Part2)")
        self.assertAlmostEqual(part2_qty, expected_part2_qty, places=2)

        print("\n✓ Path collection correctly identified all paths")
        print("✓ Part1 has 2 paths (through both SubAssemblies)")
        print("✓ Other parts have correct number of paths")
        print("✓ Cumulative quantities calculated correctly")
        print("-"*80)

    def test_04_bottom_up_attribute_calculation(self):
        """Test that bottom-up attribute calculation works correctly"""
        print("\n" + "-"*80)
        print("TEST 04: Bottom-Up Attribute Calculation")
        print("-"*80)

        from ..utils.kojto_products_graph_utils import resolve_graph
        from ..utils.kojto_products_collect_revision_paths import collect_revision_paths
        from ..utils.kojto_products_calculate_revision_attributes import calculate_revision_attributes

        visited, edges, aggregated_attributes, lock_status = resolve_graph(
            start_revision=self.rev_assembly,
            env=self.env,
            mode='tree'
        )

        revision_map = {
            rev.id: rev for rev in self.env['kojto.product.component.revision'].browse(visited)
            if rev.exists()
        }

        paths, quantities, link_quantities = collect_revision_paths(
            self.rev_assembly.id, edges, revision_map, self.env
        )

        # Calculate bottom-up attributes for each revision
        print("\nCalculating bottom-up attributes...")

        # Part1 and Part2 (leaf nodes)
        part1_weight, part1_length, part1_area, part1_volume, part1_price, part1_time, part1_other = \
            calculate_revision_attributes(self.rev_part1.id, paths, quantities, link_quantities, revision_map)

        print(f"\nPart1 bottom-up calculation:")
        print(f"  Weight: {part1_weight} (expected: 2.0 - own attributes only)")
        print(f"  Price: {part1_price} (expected: 20.0)")
        self.assertAlmostEqual(part1_weight, 2.0, places=2)
        self.assertAlmostEqual(part1_price, 20.0, places=2)

        part2_weight, part2_length, part2_area, part2_volume, part2_price, part2_time, part2_other = \
            calculate_revision_attributes(self.rev_part2.id, paths, quantities, link_quantities, revision_map)

        print(f"\nPart2 bottom-up calculation:")
        print(f"  Weight: {part2_weight} (expected: 3.0 - own attributes only)")
        print(f"  Price: {part2_price} (expected: 30.0)")
        self.assertAlmostEqual(part2_weight, 3.0, places=2)
        self.assertAlmostEqual(part2_price, 30.0, places=2)

        # SubAssembly1 - should aggregate its children
        subasm1_weight, subasm1_length, subasm1_area, subasm1_volume, subasm1_price, subasm1_time, subasm1_other = \
            calculate_revision_attributes(self.rev_subassembly1.id, paths, quantities, link_quantities, revision_map)

        expected_subasm1_weight = 10.0 + (3 * 2.0) + (2 * 3.0)  # 10 + 6 + 6 = 22
        expected_subasm1_price = 100.0 + (3 * 20.0) + (2 * 30.0)  # 100 + 60 + 60 = 220

        print(f"\nSubAssembly1 bottom-up calculation:")
        print(f"  Weight: {subasm1_weight} (expected: {expected_subasm1_weight})")
        print(f"  Calculation: 10.0 (own) + 3×2.0 (Part1) + 2×3.0 (Part2)")
        print(f"  Price: {subasm1_price} (expected: {expected_subasm1_price})")
        self.assertAlmostEqual(subasm1_weight, expected_subasm1_weight, places=2)
        self.assertAlmostEqual(subasm1_price, expected_subasm1_price, places=2)

        # SubAssembly2
        subasm2_weight, subasm2_length, subasm2_area, subasm2_volume, subasm2_price, subasm2_time, subasm2_other = \
            calculate_revision_attributes(self.rev_subassembly2.id, paths, quantities, link_quantities, revision_map)

        expected_subasm2_weight = 15.0 + (4 * 2.0)  # 15 + 8 = 23
        expected_subasm2_price = 150.0 + (4 * 20.0)  # 150 + 80 = 230

        print(f"\nSubAssembly2 bottom-up calculation:")
        print(f"  Weight: {subasm2_weight} (expected: {expected_subasm2_weight})")
        print(f"  Calculation: 15.0 (own) + 4×2.0 (Part1)")
        print(f"  Price: {subasm2_price} (expected: {expected_subasm2_price})")
        self.assertAlmostEqual(subasm2_weight, expected_subasm2_weight, places=2)
        self.assertAlmostEqual(subasm2_price, expected_subasm2_price, places=2)

        # Assembly (root)
        assembly_weight, assembly_length, assembly_area, assembly_volume, assembly_price, assembly_time, assembly_other = \
            calculate_revision_attributes(self.rev_assembly.id, paths, quantities, link_quantities, revision_map)

        expected_assembly_weight = 50.0 + (2 * 22.0) + (1 * 23.0)  # 50 + 44 + 23 = 117
        expected_assembly_price = 500.0 + (2 * 220.0) + (1 * 230.0)  # 500 + 440 + 230 = 1170

        print(f"\nAssembly bottom-up calculation:")
        print(f"  Weight: {assembly_weight} (expected: {expected_assembly_weight})")
        print(f"  Calculation: 50.0 (own) + 2×22.0 (SubAssembly1 total) + 1×23.0 (SubAssembly2 total)")
        print(f"  Price: {assembly_price} (expected: {expected_assembly_price})")
        self.assertAlmostEqual(assembly_weight, expected_assembly_weight, places=2)
        self.assertAlmostEqual(assembly_price, expected_assembly_price, places=2)

        print("\n✓ Bottom-up attribute calculation correct for all nodes")
        print("✓ Leaf nodes return their own attributes")
        print("✓ Parent nodes correctly aggregate children with quantities")
        print("✓ Root node matches top-down calculation")
        print("-"*80)

    def test_05_top_down_bottom_up_consistency(self):
        """Test that top-down and bottom-up calculations produce consistent results"""
        print("\n" + "-"*80)
        print("TEST 05: Top-Down and Bottom-Up Consistency")
        print("-"*80)

        from ..utils.kojto_products_graph_utils import resolve_graph
        from ..utils.kojto_products_collect_revision_paths import collect_revision_paths
        from ..utils.kojto_products_calculate_revision_attributes import calculate_revision_attributes

        # Get top-down results
        visited, edges, aggregated_attributes, lock_status = resolve_graph(
            start_revision=self.rev_assembly,
            env=self.env,
            mode='tree'
        )

        # Get bottom-up results
        revision_map = {
            rev.id: rev for rev in self.env['kojto.product.component.revision'].browse(visited)
            if rev.exists()
        }

        paths, quantities, link_quantities = collect_revision_paths(
            self.rev_assembly.id, edges, revision_map, self.env
        )

        print("\nComparing top-down vs bottom-up calculations for each node:")
        print("="*80)

        all_consistent = True
        for rev_id in visited:
            rev = revision_map.get(rev_id)
            if not rev:
                continue

            # Top-down attributes
            top_down_attrs = aggregated_attributes[rev_id]

            # Bottom-up attributes
            bottom_up_weight, bottom_up_length, bottom_up_area, bottom_up_volume, \
                bottom_up_price, bottom_up_time, bottom_up_other = \
                calculate_revision_attributes(rev_id, paths, quantities, link_quantities, revision_map)

            # Compare
            weight_match = abs(top_down_attrs['weight'] - bottom_up_weight) < 0.01
            price_match = abs(top_down_attrs['price'] - bottom_up_price) < 0.01

            print(f"\n{rev.name}:")
            print(f"  Weight - Top-down: {top_down_attrs['weight']:.2f}, Bottom-up: {bottom_up_weight:.2f} {'✓' if weight_match else '✗'}")
            print(f"  Price  - Top-down: {top_down_attrs['price']:.2f}, Bottom-up: {bottom_up_price:.2f} {'✓' if price_match else '✗'}")

            self.assertAlmostEqual(top_down_attrs['weight'], bottom_up_weight, places=2,
                                   msg=f"Weight mismatch for {rev.name}")
            self.assertAlmostEqual(top_down_attrs['length'], bottom_up_length, places=2,
                                   msg=f"Length mismatch for {rev.name}")
            self.assertAlmostEqual(top_down_attrs['area'], bottom_up_area, places=2,
                                   msg=f"Area mismatch for {rev.name}")
            self.assertAlmostEqual(top_down_attrs['volume'], bottom_up_volume, places=2,
                                   msg=f"Volume mismatch for {rev.name}")
            self.assertAlmostEqual(top_down_attrs['price'], bottom_up_price, places=2,
                                   msg=f"Price mismatch for {rev.name}")
            self.assertAlmostEqual(top_down_attrs['time'], bottom_up_time, places=2,
                                   msg=f"Time mismatch for {rev.name}")
            self.assertAlmostEqual(top_down_attrs['other'], bottom_up_other, places=2,
                                   msg=f"Other mismatch for {rev.name}")

        print("\n" + "="*80)
        print("✓ Top-down and bottom-up calculations are consistent")
        print("✓ All attributes match across both approaches")
        print("✓ Both methods produce the same aggregated values")
        print("-"*80)

    def test_06_cycle_detection(self):
        """Test that cycle detection works correctly"""
        print("\n" + "-"*80)
        print("TEST 06: Cycle Detection")
        print("-"*80)

        from ..utils.kojto_products_graph_utils import resolve_graph

        # Create a circular dependency: PartA -> PartB -> PartA
        component_partA = self.env['kojto.product.component'].create({
            'name': 'PartA_Cycle',
            'unit_id': self.unit_pcs.id,
            'subcode_id': self.subcode_test.id,
        })
        component_partB = self.env['kojto.product.component'].create({
            'name': 'PartB_Cycle',
            'unit_id': self.unit_pcs.id,
            'subcode_id': self.subcode_test.id,
        })

        # Use auto-created revisions
        rev_partA = component_partA.latest_revision_id
        rev_partA.write({'weight_attribute': 1.0})

        rev_partB = component_partB.latest_revision_id
        rev_partB.write({'weight_attribute': 2.0})

        # Create first link (should succeed)
        link_A_to_B = self.env['kojto.product.component.revision.link'].with_context(skip_cycle_check=True).create({
            'source_revision_id': rev_partA.id,
            'target_subcode_id': self.subcode_test.id,
            'target_component_id': component_partB.id,
            'quantity': 1.0,
        })
        print("Created link: PartA → PartB")

        # Try to create second link (should fail due to cycle detection)
        print("Attempting to create cycle: PartB → PartA")
        cycle_detected = False
        error_message = ""

        try:
            link_B_to_A = self.env['kojto.product.component.revision.link'].create({
                'source_revision_id': rev_partB.id,
                'target_subcode_id': self.subcode_test.id,
                'target_component_id': component_partA.id,
                'quantity': 1.0,
            })
            print("ERROR: Cycle was not detected! Link created successfully (should have failed)")
        except (ValidationError, UserError) as e:
            cycle_detected = True
            error_message = str(e)
            print(f"✓ Cycle detected and prevented: {error_message[:100]}...")

        self.assertTrue(cycle_detected, "Should prevent cycle creation")
        self.assertTrue('cycle' in error_message.lower(), "Error should mention cycle")

        # Cleanup - delete link first, then components (cascade to revisions)
        if link_A_to_B.exists():
            link_A_to_B.with_context(skip_cycle_check=True).unlink()

        # Force delete components even if there are link references
        # Search and delete any remaining links to these components
        remaining_links = self.env['kojto.product.component.revision.link'].search([
            '|', ('target_component_id', 'in', [component_partA.id, component_partB.id]),
            ('source_revision_id.component_id', 'in', [component_partA.id, component_partB.id])
        ])
        if remaining_links:
            remaining_links.with_context(skip_cycle_check=True).unlink()

        component_partA.unlink()  # Deletes revisions via cascade
        component_partB.unlink()  # Deletes revisions via cascade

        print("\n✓ Cycle detection working correctly")
        print("✓ Circular dependencies are prevented at link creation")
        print("✓ Appropriate error message displayed")
        print("-"*80)

    def test_07_empty_graph(self):
        """Test behavior with a single node (no children)"""
        print("\n" + "-"*80)
        print("TEST 07: Empty Graph (Single Node)")
        print("-"*80)

        from ..utils.kojto_products_graph_utils import resolve_graph
        from ..utils.kojto_products_collect_revision_paths import collect_revision_paths

        # Create a standalone component with no children
        component_single = self.env['kojto.product.component'].create({
            'name': 'SinglePart',
            'unit_id': self.unit_pcs.id,
            'subcode_id': self.subcode_test.id,
        })

        # Use auto-created revision
        rev_single = component_single.latest_revision_id
        rev_single.write({
            'weight_attribute': 5.0,
            'price_attribute': 50.0,
        })

        print("Created standalone component with no children")

        # Test graph resolution
        visited, edges, aggregated_attributes, lock_status = resolve_graph(
            start_revision=rev_single,
            env=self.env,
            mode='tree'
        )

        print(f"\nVisited nodes: {len(visited)} (expected: 1)")
        print(f"Edges: {len(edges)} (expected: 0)")

        self.assertEqual(len(visited), 1, "Should visit only 1 node")
        self.assertEqual(len(edges), 0, "Should have no edges")
        self.assertIn(rev_single.id, visited)

        # Test attributes
        single_attrs = aggregated_attributes[rev_single.id]
        print(f"\nSinglePart attributes:")
        print(f"  Weight: {single_attrs['weight']} (expected: 5.0)")
        print(f"  Price: {single_attrs['price']} (expected: 50.0)")

        self.assertAlmostEqual(single_attrs['weight'], 5.0, places=2)
        self.assertAlmostEqual(single_attrs['price'], 50.0, places=2)

        # Test path collection
        revision_map = {rev_single.id: rev_single}
        paths, quantities, link_quantities = collect_revision_paths(
            rev_single.id, edges, revision_map, self.env
        )

        print(f"\nPaths collected: {len(paths[rev_single.id])} (expected: 1)")
        self.assertEqual(len(paths[rev_single.id]), 1, "Should have 1 path (itself)")

        # Cleanup (delete component first, revision cascades)
        component_single.unlink()  # Deletes revisions via cascade

        print("\n✓ Empty graph handled correctly")
        print("✓ Single node returns only its own attributes")
        print("✓ No errors with zero edges")
        print("-"*80)

    def test_08_html_formatting(self):
        """Test that HTML formatting functions execute without errors"""
        print("\n" + "-"*80)
        print("TEST 08: HTML Formatting")
        print("-"*80)

        from ..utils.kojto_products_graph_utils import resolve_graph
        from ..utils.kojto_products_collect_revision_paths import collect_revision_paths
        from ..utils.kojto_products_export_html import format_top_down, format_bottom_up

        visited, edges, aggregated_attributes, lock_status = resolve_graph(
            start_revision=self.rev_assembly,
            env=self.env,
            mode='tree'
        )

        revision_map = {
            rev.id: rev for rev in self.env['kojto.product.component.revision'].browse(visited)
            if rev.exists()
        }

        paths, quantities, link_quantities = collect_revision_paths(
            self.rev_assembly.id, edges, revision_map, self.env
        )

        # Test top-down HTML formatting
        print("\nTesting top-down HTML formatting...")
        top_down_html = format_top_down(
            edges, visited, aggregated_attributes, revision_map,
            self.env, self.rev_assembly.id, lock_status
        )

        self.assertIsNotNone(top_down_html, "Top-down HTML should not be None")
        self.assertGreater(len(str(top_down_html)), 0, "Top-down HTML should not be empty")
        self.assertIn('Assembly', str(top_down_html), "HTML should contain Assembly")
        print(f"✓ Top-down HTML generated ({len(str(top_down_html))} characters)")

        # Test bottom-up HTML formatting
        print("Testing bottom-up HTML formatting...")
        bottom_up_html = format_bottom_up(
            self.rev_assembly, paths, quantities, link_quantities,
            revision_map, lock_status
        )

        self.assertIsNotNone(bottom_up_html, "Bottom-up HTML should not be None")
        self.assertGreater(len(str(bottom_up_html)), 0, "Bottom-up HTML should not be empty")
        self.assertIn('Assembly', str(bottom_up_html), "HTML should contain Assembly")
        print(f"✓ Bottom-up HTML generated ({len(str(bottom_up_html))} characters)")

        print("\n✓ HTML formatting functions work correctly")
        print("✓ Both top-down and bottom-up HTML generated")
        print("✓ No errors during formatting")
        print("-"*80)

