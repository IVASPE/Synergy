from django import template
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import get_model
import re
import copy

from synergy.contrib.records.models import get_parent_field
from django.utils.datastructures import SortedDict

register = template.Library()

@register.filter(name='teaser')
def teaser(obj):
    app_label = obj._meta.app_label
    model = obj._meta.object_name.lower()
    tpl = '%s/teasers/%s.html' % (obj._meta.app_label, obj._meta.object_name.lower())
    try:
        if settings.DEBUG:
            print tpl
        return render_to_string(tpl, {model: obj})
    except template.TemplateDoesNotExist:
        tpl = 'synergy/contrib/prospects/teaser.html'
        return render_to_string(tpl, {'object': obj})


@register.filter(name='fields')
def fields(obj, object_detail):

    context = {'model_fields': SortedDict(), 'object_fields': SortedDict(), 'object': obj, 'object_detail': object_detail,
               'object_name':obj._meta.verbose_name
               }

    for field in filter(lambda x: x.name != 'id', obj._meta.fields):
        context['model_fields'][field.verbose_name] = getattr(obj, field.name)

    for field in object_detail.fields.all():
        context['object_fields'][field.field] = field.field.get_value(obj)

    tpl = 'prospects/rendering/objectdetail/fields.html'
    return render_to_string(tpl, context)

class VariantsNode(template.Node):
    def __init__(self, format_string, var_name):
        self.format_string = format_string
        self.var_name = var_name
    def render(self, context):
        model = {'variants': 'ProspectVariant'}[self.var_name]
        context[self.var_name] = get_model('prospects', model).objects.all()
        return ''

@register.tag
def get_prospect(parser, token):
    # This version uses a regular expression to parse tag contents.
    try:
        # Splitting by None == splitting by spaces.
        tag_name, arg = token.contents.split(None, 1)
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires arguments" % token.contents.split()[0])
    m = re.search(r'(.*?) as (\w+)', arg)
    if not m:
        raise template.TemplateSyntaxError("%r tag had invalid arguments" % tag_name)
    format_string, var_name = m.groups()
#    if not (format_string[0] == format_string[-1] and format_string[0] in ('"', "'")):
#        raise template.TemplateSyntaxError("%r tag's argument should be in quotes" % tag_name)
    return VariantsNode(format_string[1:-1], var_name)



class VariantResultsNode(template.Node):
    def __init__(self, variant, user, query):
        self.variant = template.Variable(variant)
        self.query = template.Variable(query)
        self.user = template.Variable(user)

    def render(self, context):
        variant = self.variant.resolve(context)
        query = self.query.resolve(context)
        user = self.user.resolve(context)

        error_info = None
        try:
            results = variant.filter(user, **query)
        except Exception, error:
            if settings.DEBUG:
                error_info = error
            results = None

        ctx = copy.copy(context)
        ctx['results'] = results
        ctx['variant'] = variant
        ctx['error'] = error_info
        repr_obj = variant.listrepresentation.representation
        ctx[repr_obj._meta.object_name.lower()] = repr_obj
        ctx.update(repr_obj.get_context_data())

        tpl = 'synergy/contrib/prospects/views/variant.html'

        return render_to_string(tpl, ctx)


@register.tag
def render_results(parser, token):
    # This version uses a regular expression to parse tag contents.
    try:
        # Splitting by None == splitting by spaces.
        tag_name, variant, user, query = token.contents.split(None, 3)
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires arguments" % token.contents.split()[0])
    return VariantResultsNode(variant, user, query)


@register.filter(name='as_record')
def as_record(obj):
    app_label = obj._meta.app_label
    model = obj._meta.object_name.lower()
    ct = get_model('contenttypes', 'contenttype').objects.get_for_model(obj)

    setup = ct.record_setup
    context = {'object': obj, 'object_name': obj._meta.verbose_name,
               'record_relations': {}, 'setup': setup}

    
    for related_model in setup.related_models.all():
        context['record_relations'][related_model] = related_model.model.model_class().objects.filter(**{related_model.setup.model.model: obj})

    tpl = 'prospects/rendering/objectdetail/object.html'
    return render_to_string(tpl, context)


@register.filter(name='model_relations')
def model_relations(obj):
    app_label = obj._meta.app_label
    model = obj._meta.object_name.lower()
    ct = get_model('contenttypes', 'contenttype').objects.get_for_model(obj)


    # Parent
    parent_field = get_parent_field(obj._meta)
    parent = {}
    if parent_field:
        parent['object'] = getattr(obj, parent_field.name)
        parent['setup'] = get_model('records', 'RecordSetup').objects.get(model__model=parent_field.rel.to._meta.object_name.lower())


    setup = ct.record_setup

    context = {'object': obj, 'object_name': obj._meta.verbose_name, 'tracked_model_relations': {}, 'untracked_model_relations': {}, 
               'record_relations': {}, 'parent': parent, 'setup': setup}

    
    for related_model in setup.related_models.all():
        context['record_relations'][related_model] = related_model.model.model_class().objects.filter(**{related_model.setup.model.model: obj})
    classes_in_record = [relation.model.model_class() for relation in context['record_relations']]
    
    db_rels = [rel for rel in obj._meta.get_all_related_objects() if not rel.model in classes_in_record]
    for rel in db_rels:
        if rel.field.rel.multiple:
            related_object = getattr(obj, rel.get_accessor_name())
        else:
            try:
                related_object = getattr(obj, rel.get_accessor_name())
            except:
                related_object = None
        try:
            context['tracked_model_relations'][rel] = {'setup': get_model('records', 'RecordSetup').objects.get(model__model=rel.var_name),
                                                       'related_object': related_object}
        except get_model('records', 'RecordSetup').DoesNotExist:
            context['untracked_model_relations'][rel] = {'related_object': related_object}

    tpl = 'prospects/rendering/objectdetail/model_relations.html'
    return render_to_string(tpl, context)
