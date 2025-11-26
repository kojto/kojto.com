# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestKojtoAssets(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestKojtoAssets, cls).setUpClass()
        print("\nSetting up test environment...")
        # Create a test unit that we'll use for the asset
        cls.test_unit = cls.env['kojto.base.units'].create({
            'name': 'Test Unit',
            'unit_type': 'quantity',  # Using a valid unit_type from the selection list
            'conversion_factor': 2.0,  # Adding a conversion factor that's not 1
        })
        print(f"Created test unit: {cls.test_unit.name}")

    @classmethod
    def tearDownClass(cls):
        print("\nCleaning up test environment...")
        if hasattr(cls, 'test_unit'):
            cls.test_unit.unlink()
            print("Deleted test unit")
        super(TestKojtoAssets, cls).tearDownClass()

    def test_01_create_asset(self):
        """Test creating a new asset"""
        print("\nRunning test_01_create_asset...")
        # Create a new asset
        asset = self.env['kojto.assets'].create({
            'name': 'Test Asset',
            'description': 'Test Description',
            'unit_id': self.test_unit.id,
        })
        print(f"Created asset: {asset.name}")

        # Verify the asset was created correctly
        self.assertEqual(asset.name, 'Test Asset')
        self.assertEqual(asset.description, 'Test Description')
        self.assertEqual(asset.unit_id, self.test_unit)
        self.assertTrue(asset.active)
        self.assertTrue(asset.guid)  # Verify GUID was generated
        print("Asset creation test passed")

    def test_02_modify_asset(self):
        """Test modifying an existing asset"""
        print("\nRunning test_02_modify_asset...")
        # Create an asset first
        asset = self.env['kojto.assets'].create({
            'name': 'Original Asset',
            'description': 'Original Description',
            'unit_id': self.test_unit.id,
        })
        print(f"Created asset: {asset.name}")

        # Modify the asset
        asset.write({
            'name': 'Modified Asset',
            'description': 'Modified Description',
        })
        print(f"Modified asset to: {asset.name}")

        # Verify the modifications
        self.assertEqual(asset.name, 'Modified Asset')
        self.assertEqual(asset.description, 'Modified Description')
        # Verify other fields remain unchanged
        self.assertEqual(asset.unit_id, self.test_unit)
        self.assertTrue(asset.active)
        print("Asset modification test passed")

    def test_03_delete_asset(self):
        """Test deleting an asset"""
        print("\nRunning test_03_delete_asset...")
        # Create an asset
        asset = self.env['kojto.assets'].create({
            'name': 'Asset to Delete',
            'description': 'Will be deleted',
            'unit_id': self.test_unit.id,
        })
        print(f"Created asset: {asset.name}")

        # Store the ID for verification
        asset_id = asset.id

        # Delete the asset
        asset.unlink()
        print("Deleted asset")

        # Verify the asset no longer exists
        deleted_asset = self.env['kojto.assets'].search([('id', '=', asset_id)])
        self.assertFalse(deleted_asset, "Asset should be deleted")
        print("Asset deletion test passed")
