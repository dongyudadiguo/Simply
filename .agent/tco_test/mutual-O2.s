	.file	"mutual.c"
	.text
	.p2align 4
	.globl	is_even
	.def	is_even;	.scl	2;	.type	32;	.endef
	.seh_proc	is_even
is_even:
	.seh_endprologue
	movl	$1, %eax
	testl	%ecx, %ecx
	je	.L1
.L3:
	cmpl	$1, %ecx
	jne	.L13
.L9:
	xorl	%eax, %eax
.L1:
	ret
	.p2align 4,,10
	.p2align 3
.L13:
	cmpl	$2, %ecx
	je	.L8
	cmpl	$3, %ecx
	je	.L9
	cmpl	$4, %ecx
	je	.L8
	cmpl	$5, %ecx
	je	.L9
	subl	$6, %ecx
	jne	.L3
.L8:
	movl	$1, %eax
	ret
	.seh_endproc
	.p2align 4
	.globl	is_odd
	.def	is_odd;	.scl	2;	.type	32;	.endef
	.seh_proc	is_odd
is_odd:
	.seh_endprologue
	testl	%ecx, %ecx
	movl	%ecx, %eax
	jne	.L27
.L15:
	ret
	.p2align 4,,10
	.p2align 3
.L27:
	cmpl	$1, %ecx
	je	.L15
	cmpl	$2, %ecx
	jne	.L28
.L20:
	xorl	%eax, %eax
	ret
	.p2align 4,,10
	.p2align 3
.L28:
	cmpl	$3, %ecx
	je	.L19
	cmpl	$4, %ecx
	je	.L20
	cmpl	$5, %ecx
	je	.L19
	cmpl	$6, %ecx
	je	.L20
	leal	-7(%rcx), %ecx
	jmp	is_even
	.p2align 4,,10
	.p2align 3
.L19:
	movl	$1, %eax
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
