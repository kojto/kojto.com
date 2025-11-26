# kojto_products/models/mixins/kojto_product_articles.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KojtoProductArticlesMixin(models.AbstractModel):
    _name = 'kojto.product.articles.mixin'
    _description = 'Kojto Product Articles Mixin'

    # Article-specific fields
    article_number = fields.Char(string='Article Number', index=True)
    article_supplier_id = fields.Many2one('kojto.contacts', string='Article Supplier')
    article_barcode = fields.Char(string='Article Barcode')
    article_package_quantity = fields.Float(string='Package Quantity', digits=(16, 4))

    # Replacement/Identical articles hierarchy
    is_parent_article = fields.Boolean(string='Is Parent Article', compute='_compute_is_parent_article', help='Indicates if this article is a parent (has other articles referencing it)')
    parent_article_id = fields.Many2one('kojto.product.component', string='Parent Article', domain=[('component_type', '=', 'article'), ('is_parent_article', '=', False), ('parent_article_id', '=', False)], help='Main article that this article can replace. All articles with the same parent are interchangeable.', index=True)
    interchangeable_article_ids = fields.Many2many('kojto.product.component', string='All Interchangeable Articles', compute='_compute_interchangeable_articles', help='All articles in the same family (parent + all siblings)')

    def _compute_is_parent_article(self):
        """Check if this article has children (other articles referencing it as parent)"""
        for record in self:
            if record.id:
                child_count = self.env['kojto.product.component'].search_count([
                    ('parent_article_id', '=', record.id)
                ])
                record.is_parent_article = child_count > 0
            else:
                record.is_parent_article = False

    @api.depends('parent_article_id')
    def _compute_interchangeable_articles(self):
        """Compute all interchangeable articles in the family"""
        for record in self:
            if record.parent_article_id:
                # If this is a child, get parent + all siblings
                siblings = self.env['kojto.product.component'].search([
                    ('parent_article_id', '=', record.parent_article_id.id),
                    ('id', '!=', record.id)
                ])
                interchangeable = record.parent_article_id | siblings
            else:
                # No family - this could be a parent or standalone
                interchangeable = self.env['kojto.product.component']
            record.interchangeable_article_ids = interchangeable

    @api.constrains('parent_article_id', 'is_parent_article')
    def _check_parent_article_hierarchy(self):
        """Ensure parent articles cannot have a parent themselves"""
        for record in self:
            if record.is_parent_article and record.parent_article_id:
                raise ValidationError(
                    'A parent article cannot have a parent article set. '
                    'This article is already a parent for other articles.'
                )


