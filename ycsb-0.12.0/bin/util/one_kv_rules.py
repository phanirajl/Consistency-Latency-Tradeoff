def one_kv_violation_fz(fz1,fz2):
	if fz1.max_start < fz2.min_finish or fz2.max_start < fz1.min_finish:
		return False
	else:
		return True

def one_kv_violation_fz_bz(fz,bz):
	if fz.min_finish < bz.max_start and fz.max_start > bz.min_finish:
		return True
	else:
		return False