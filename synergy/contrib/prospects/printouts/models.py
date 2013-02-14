from django.db import models
from django.utils.translation import ugettext_lazy as _
from synergy.models.current_user.models import CurrentUserField
from uuid import uuid4
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os

class VariantPDF(models.Model):
    CHOICES = ( ('d','detail'), ('l','list') )
    name = models.SlugField(max_length=128, unique=True)
    variant = models.ForeignKey('prospects.ProspectVariant', related_name="pdfs")
    tpl = models.ForeignKey('pdfgen.PDFTemplate', related_name='variant_pdfs')
    mode = models.CharField(max_length=1, verbose_name="Template mode", choices=CHOICES)
    is_variant_action = models.BooleanField(verbose_name="Is variant action")
    custom_action_name = models.CharField(max_length=50, blank=True, verbose_name="Custom action name")
    is_stored = models.BooleanField()

    def get_action_name(self):
        if self.custom_action_name:
            return self.custom_action_name
        if self.mode == 'l':
            return _("PDF list %s " % self.tpl.verbose_name)
        else:
            return _("PDF detail list %s" % self.tpl.verbose_name)

    def __unicode__(self):
        return self.variant.__unicode__() + ' PDFs'

    class Meta:
        verbose_name = "PDF"
        unique_together = (('variant', 'tpl'), )


files_location = os.path.join(settings.MEDIA_ROOT)
file_system_storage = FileSystemStorage(location=files_location, base_url=settings.MEDIA_URL)

def pdf_save(instance, filename):
    return  os.path.join("%s" % settings.PDF_STORAGE_PATH, '%s.pdf' % uuid4() )

class PDFFile(models.Model):
    uuid = models.CharField(max_length=36, db_index=True)
    pdf = models.FileField(upload_to = pdf_save, storage = file_system_storage)
    date = models.DateField(auto_now_add=True)
    user = CurrentUserField()

    def get_filename(self):
        return self.pdf.name.split('/')[-1].split('.')[0]

    def save(self, *args, **kwargs):
        self.uuid = self.get_filename
        super(PDFFile, self).save(*args, **kwargs)

