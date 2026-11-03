import torch,json
torch.set_num_threads(1)
output={}
for method in ("single","batch"):
 torch.manual_seed(42);bias=torch.nn.Parameter(torch.zeros(()));opt=torch.optim.AdamW([bias],lr=.003,weight_decay=0.)
 for epoch in range(2000):
  if method=="single":
   for label in torch.tensor([0.,0.,1.])[torch.randperm(3)]:
    opt.zero_grad();loss=torch.nn.functional.binary_cross_entropy_with_logits(bias,label)*(1.5 if label else .75);loss.backward();torch.nn.utils.clip_grad_norm_([bias],1.);opt.step()
  else:
   opt.zero_grad();loss=(torch.nn.functional.binary_cross_entropy_with_logits(bias.expand(3),torch.tensor([0.,0.,1.]),reduction="none")*torch.tensor([.75,.75,1.5])).mean();loss.backward();torch.nn.utils.clip_grad_norm_([bias],1.);opt.step()
 output[method]=float(bias.detach().sigmoid())
print(output)
open('data/training_audit_v3/optimizer_control.json','w').write(json.dumps(output,indent=2))
