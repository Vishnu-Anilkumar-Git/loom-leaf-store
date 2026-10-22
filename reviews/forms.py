from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(5, "5 — Excellent"), (4, "4 — Good"), (3, "3 — Average"),
                 (2, "2 — Below expectations"), (1, "1 — Poor")],
        widget=forms.RadioSelect(attrs={"class": "rating-input"}),
    )

    class Meta:
        model = Review
        fields = ["rating", "title", "body"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional headline"}
            ),
            "body": forms.Textarea(
                attrs={"class": "form-control", "rows": 4,
                       "placeholder": "How does it fit? How does it feel?"}
            ),
        }

    def clean_rating(self):
        try:
            rating = int(self.cleaned_data["rating"])
        except (TypeError, ValueError):
            raise forms.ValidationError("Choose a rating between 1 and 5.")
        if rating not in range(1, 6):
            raise forms.ValidationError("Choose a rating between 1 and 5.")
        return rating

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if len(body) < 10:
            raise forms.ValidationError("Please write at least 10 characters.")
        return body
