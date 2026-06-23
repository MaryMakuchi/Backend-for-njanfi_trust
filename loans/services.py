def max_eligible_amount(user):
    mri = float(user.mri_score)
    if mri >= 9.0:
        return 500000
    if mri >= 8.0:
        return 350000
    if mri >= 7.0:
        return 200000
    return 100000
