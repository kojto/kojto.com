#!/usr/bin/env python3
"""
Test script to understand pynest2d API
Run this in the Odoo venv to see what methods are available
"""

import sys
print(f"Python: {sys.executable}")
print(f"Python version: {sys.version}")
print()

try:
    import pynest2d
    print("✓ pynest2d imported successfully")
    print(f"Location: {pynest2d.__file__}")
    print()

    print("Available pynest2d attributes:")
    attrs = [x for x in dir(pynest2d) if not x.startswith('_')]
    for attr in attrs:
        print(f"  - {attr}")
    print()

    # Try to use the nest function (functional API)
    print("Testing nest function:")
    if hasattr(pynest2d, 'nest'):
        print("  ✓ Found nest function")
        print(f"  nest type: {type(pynest2d.nest)}")
        try:
            import inspect
            sig = inspect.signature(pynest2d.nest)
            print(f"  nest signature: {sig}")
        except:
            pass
        print()

    # Try to create a Box/Rectangle for bin
    print("Testing Box/Rectangle creation (for bins):")
    if hasattr(pynest2d, 'Box'):
        try:
            box = pynest2d.Box(1000, 2000)
            print(f"  ✓ Created Box(1000, 2000): {box}")
            print(f"  Box type: {type(box)}")
            print(f"  Box methods: {[x for x in dir(box) if not x.startswith('_')]}")
        except Exception as e:
            print(f"  ✗ Box creation failed: {e}")
    if hasattr(pynest2d, 'Rectangle'):
        try:
            rect = pynest2d.Rectangle(1000, 2000)
            print(f"  ✓ Created Rectangle(1000, 2000): {rect}")
            print(f"  Rectangle type: {type(rect)}")
        except Exception as e:
            print(f"  ✗ Rectangle creation failed: {e}")
    print()

    # Try to create a Nest object (if it exists)
    print("Testing Nest class (if exists):")
    if hasattr(pynest2d, 'Nest'):
        try:
            nest = pynest2d.Nest()
            print("  ✓ Created nest using pynest2d.Nest()")
            print(f"  Nest type: {type(nest)}")
            print()

            print("  Nest methods:")
            nest_methods = [x for x in dir(nest) if not x.startswith('_')]
            for method in nest_methods:
                print(f"    - {method}")
            print()

            # Try to add a bin
            print("  Testing add_bin:")
            if hasattr(nest, 'add_bin'):
                try:
                    nest.add_bin(1000, 2000)
                    print("    ✓ add_bin(1000, 2000) succeeded")
                except Exception as e:
                    print(f"    ✗ add_bin failed: {e}")
            elif hasattr(nest, 'addBin'):
                try:
                    nest.addBin(1000, 2000)
                    print("    ✓ addBin(1000, 2000) succeeded")
                except Exception as e:
                    print(f"    ✗ addBin failed: {e}")
            else:
                print("    ✗ No add_bin or addBin method found")
            print()

            # Try to create an Item with polygon points (free geometry)
            print("  Testing Item creation with polygon points (free geometry):")
            if hasattr(pynest2d, 'Item'):
                try:
                    # Test Point creation first
                    print("    Testing Point creation:")
                    if hasattr(pynest2d, 'Point'):
                        try:
                            point = pynest2d.Point(0, 0)
                            print(f"      ✓ Created Point(0, 0): {point}")
                            print(f"      Point type: {type(point)}")
                        except Exception as e:
                            print(f"      ✗ Point creation failed: {e}")

                    # Try creating Item with polygon points (free geometry)
                    # First try with Point objects (most likely format)
                    points_list = [(0, 0), (100, 0), (100, 50), (0, 50)]
                    print(f"    Trying to create Item with polygon points: {points_list}")

                    item = None
                    if hasattr(pynest2d, 'Point'):
                        try:
                            point_objects = [pynest2d.Point(x, y) for x, y in points_list]
                            item = pynest2d.Item(point_objects)
                            print(f"    ✓ Created Item with Point objects (polygon)")
                            print(f"    Item type: {type(item)}")
                        except Exception as e:
                            print(f"    ✗ Item creation with Point objects failed: {e}")
                            import traceback
                            traceback.print_exc()

                    # Try with tuple list if Point objects didn't work
                    if item is None:
                        try:
                            item = pynest2d.Item(points_list)
                            print(f"    ✓ Created Item with tuple list")
                            print(f"    Item type: {type(item)}")
                        except Exception as e:
                            print(f"    ✗ Item creation with tuple list failed: {e}")
                            import traceback
                            traceback.print_exc()

                    if item:
                        print()
                        print("    Item methods:")
                        item_methods = [x for x in dir(item) if not x.startswith('_')]
                        for method in item_methods:
                            print(f"      - {method}")
                        print()

                        # Try functional API - call nest() function directly
                        if hasattr(pynest2d, 'nest'):
                            print("  Testing functional nest() API with free geometry:")
                            try:
                                # Create a bin (Box or Rectangle)
                                bin_obj = None
                                if hasattr(pynest2d, 'Box'):
                                    try:
                                        bin_obj = pynest2d.Box(1000, 2000)
                                        print(f"    ✓ Created Box(1000, 2000) as bin")
                                    except Exception as e:
                                        print(f"    ✗ Box creation failed: {e}")
                                elif hasattr(pynest2d, 'Rectangle'):
                                    try:
                                        bin_obj = pynest2d.Rectangle(1000, 2000)
                                        print(f"    ✓ Created Rectangle(1000, 2000) as bin")
                                    except Exception as e:
                                        print(f"    ✗ Rectangle creation failed: {e}")

                                if bin_obj:
                                    # Try calling nest function with items and bins
                                    print("    Trying nest(items, bins, config):")
                                    try:
                                        # Try different parameter combinations
                                        items_list = [item]
                                        bins_list = [bin_obj]

                                        # Try with config
                                        config = None
                                        if hasattr(pynest2d, 'BottomLeftConfig'):
                                            try:
                                                config = pynest2d.BottomLeftConfig()
                                                print(f"      ✓ Created BottomLeftConfig")
                                            except Exception as e:
                                                print(f"      ✗ BottomLeftConfig creation failed: {e}")

                                        # Try DJDHeuristicConfig as alternative
                                        if config is None and hasattr(pynest2d, 'DJDHeuristicConfig'):
                                            try:
                                                config = pynest2d.DJDHeuristicConfig()
                                                print(f"      ✓ Created DJDHeuristicConfig")
                                            except Exception as e:
                                                print(f"      ✗ DJDHeuristicConfig creation failed: {e}")

                                        # Call nest function - try different signatures
                                        result = None
                                        try:
                                            # Try with config
                                            if config:
                                                result = pynest2d.nest(items_list, bins_list, config)
                                                print(f"    ✓ nest(items, bins, config) succeeded!")
                                            else:
                                                result = pynest2d.nest(items_list, bins_list)
                                                print(f"    ✓ nest(items, bins) succeeded!")
                                        except TypeError as e:
                                            # Try different parameter order or format
                                            print(f"    First attempt failed: {e}")
                                            try:
                                                # Maybe it's nest(bins, items)?
                                                result = pynest2d.nest(bins_list, items_list)
                                                print(f"    ✓ nest(bins, items) succeeded!")
                                            except Exception as e2:
                                                print(f"    ✗ Alternative parameter order failed: {e2}")
                                                raise e

                                        print(f"    Result type: {type(result)}")
                                        print(f"    Result: {result}")

                                        if result:
                                            if isinstance(result, (list, tuple)):
                                                print(f"    Result length: {len(result)}")
                                                if len(result) > 0:
                                                    print(f"    First result: {result[0]}")
                                                    print(f"    First result type: {type(result[0])}")
                                                    if hasattr(result[0], '__dict__'):
                                                        print(f"    First result attributes: {result[0].__dict__}")
                                                    print(f"    First result dir: {[x for x in dir(result[0]) if not x.startswith('_')]}")

                                                    # Try to access common attributes
                                                    if hasattr(result[0], 'x') or hasattr(result[0], 'X'):
                                                        x_attr = 'x' if hasattr(result[0], 'x') else 'X'
                                                        y_attr = 'y' if hasattr(result[0], 'y') else 'Y'
                                                        print(f"    Position: x={getattr(result[0], x_attr)}, y={getattr(result[0], y_attr)}")
                                            elif hasattr(result, '__dict__'):
                                                print(f"    Result attributes: {result.__dict__}")
                                            print(f"    Result dir: {[x for x in dir(result) if not x.startswith('_')]}")

                                    except Exception as e:
                                        print(f"    ✗ nest() function call failed: {e}")
                                        import traceback
                                        traceback.print_exc()
                            except Exception as e:
                                print(f"  ✗ Functional API test failed: {e}")
                                import traceback
                                traceback.print_exc()
                except Exception as e:
                    print(f"  ✗ Item creation test failed: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("  ✗ No Item class found in pynest2d")

        except Exception as e:
            print(f"  ✗ Nest creation failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("  ✗ No Nest class found in pynest2d")

except ImportError as e:
    print(f"✗ Failed to import pynest2d: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

