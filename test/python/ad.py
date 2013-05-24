#
#     This file is part of CasADi.
# 
#     CasADi -- A symbolic framework for dynamic optimization.
#     Copyright (C) 2010 by Joel Andersson, Moritz Diehl, K.U.Leuven. All rights reserved.
# 
#     CasADi is free software; you can redistribute it and/or
#     modify it under the terms of the GNU Lesser General Public
#     License as published by the Free Software Foundation; either
#     version 3 of the License, or (at your option) any later version.
# 
#     CasADi is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#     Lesser General Public License for more details.
# 
#     You should have received a copy of the GNU Lesser General Public
#     License along with CasADi; if not, write to the Free Software
#     Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
# 
# 
from casadi import *
import casadi as c
from numpy import *
import unittest
from types import *
from helpers import *
import itertools

@run_only(["MX"])
class ADtests(casadiTestCase):

  def setUp(self):
    x=SX("x")
    y=SX("y")
    z=SX("z")
    w=SX("w")
    
    out=SXMatrix(6,1)
    out[0,0]=x
    out[2,0]=x+2*y**2
    out[4,0]=x+2*y**3+3*z**4
    out[5,0]=w

    inp=SXMatrix(6,1)
    inp[0,0]=x
    inp[2,0]=y
    inp[4,0]=z
    inp[5,0]=w
    
    sp = CRSSparsity(6,1,[0, 0, 0, 0],[0, 1, 1, 2, 2, 3, 4])
    spT = CRSSparsity(1,6,[0, 2, 4, 5],[0, 4])
    
    self.sxinputs = {
       "column" : {
            "dense": [vertcat([x,y,z,w])],
            "sparse": [inp] }
        , "row": {
            "dense":  [SXMatrix([x,y,z,w]).T],
            "sparse": [inp.T]
       }, "matrix": {
          "dense": [c.reshape(SXMatrix([x,y,z,w]),2,2)],
          "sparse": [c.reshape(inp,3,2)]
        }
    }

    self.mxinputs = {
       "column" : {
            "dense": [MX("xyzw",4,1)],
            "sparse": [MX("xyzw",sp)]
        },
        "row" : {
            "dense": [MX("xyzw",1,4)],
            "sparse": [MX("xyzw",spT)]
        },
        "matrix": {
            "dense": [MX("xyzw",2,2)],
            "sparse": [MX("xyzw",c.reshape(inp,3,2).sparsity())]
        }
    }
    
    def temp1(xyz):
      X=MX(6,1)
      X[0,0]=xyz[0]
      X[2,0]=xyz[0]+2*xyz[1]**2
      X[4,0]=xyz[0]+2*xyz[1]**3+3*xyz[2]**4
      X[5,0]=xyz[3]
      return [X]
    
    def temp2(xyz):
      X=MX(1,6)
      X[0,0]=xyz[0]
      X[0,2]=xyz[0]+2*xyz[1]**2
      X[0,4]=xyz[0]+2*xyz[1]**3+3*xyz[2]**4
      X[0,5]=xyz[3]
      return [X]

    def testje(xyz):
      print vertcat([xyz[0],xyz[0]+2*xyz[1]**2,xyz[0]+2*xyz[1]**3+3*xyz[2]**4,xyz[3]]).shape
      
    self.mxoutputs = {
       "column": {
        "dense":  lambda xyz: [vertcat([xyz[0],xyz[0]+2*xyz[1]**2,xyz[0]+2*xyz[1]**3+3*xyz[2]**4,xyz[3]])],
        "sparse": temp1
        }, "row": {
        "dense": lambda xyz: [horzcat([xyz[0],xyz[0]+2*xyz[1]**2,xyz[0]+2*xyz[1]**3+3*xyz[2]**4,xyz[3]])],
        "sparse": temp2
       },
       "matrix": {
          "dense": lambda xyz: [c.reshape(vertcat([xyz[0],xyz[0]+2*xyz[1]**2,xyz[0]+2*xyz[1]**3+3*xyz[2]**4,xyz[3]]),(2,2))],
          "sparse": lambda xyz: [c.reshape(temp1(xyz)[0],(3,2))]
       }
    }


    self.sxoutputs = {
       "column": {
        "dense": [vertcat([x,x+2*y**2,x+2*y**3+3*z**4,w])],
        "sparse": [out]
        }, "row": {
          "dense":  [SXMatrix([x,x+2*y**2,x+2*y**3+3*z**4,w]).T],
          "sparse": [out.T]
      }, "matrix" : {
          "dense":  [c.reshape(SXMatrix([x,x+2*y**2,x+2*y**3+3*z**4,w]),2,2)],
          "sparse": [c.reshape(out,3,2)]
      }
    }
    
    self.jacobians = {
      "dense" : {
        "dense" : lambda x,y,z,w: array([[1,0,0,0],[1,4*y,0,0],[1,6*y**2,12*z**3,0],[0,0,0,1]]),
        "sparse" : lambda x,y,z,w: array([[1,0,0,0],[0,0,0,0],[1,4*y,0,0],[0,0,0,0],[1,6*y**2,12*z**3,0],[0,0,0,1]])
        }
      ,
      "sparse" : {
        "dense" : lambda x,y,z,w: array([[1,0,0,0,0,0],[1,0,4*y,0,0,0],[1,0,6*y**2,0,12*z**3,0],[0,0,0,0,0,1]]),
        "sparse" : lambda x,y,z,w:  array([[1,0,0,0,0,0],[0,0,0,0,0,0],[1,0,4*y,0,0,0],[0,0,0,0,0,0],[1,0,6*y**2,0,12*z**3,0],[0,0,0,0,0,1]])
      }
    }
  
  
  def test_fwd(self):
    n=array([1.2,2.3,7,1.4])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["sparse","dense"]:
          for outputtype in ["sparse","dense"]:
            self.message("fwd AD on SX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=SXFunction(self.sxinputs[inputshape][inputtype],self.sxoutputs[outputshape][outputtype])
            f.init()
            f.input().set(n)
            self.assertEqual(f.fwdSeed().shape,f.input().shape,"fwdSeed shape")
            self.assertEqual(f.fwdSeed().size(),f.input().size(),"fwdSeed shape")
            J = self.jacobians[inputtype][outputtype](*n)
            for d in [array([1,0,0,0]),array([0,2,0,0]),array([1.2,4.8,7.9,4.6])]:
              f.fwdSeed().set(d)
              f.evaluate(1,0)
              seed = array(f.fwdSeed()).ravel()
              sens = array(f.fwdSens()).ravel()
              self.checkarray(sens,dot(J,seed),"AD")

  def test_adj(self):
    n=array([1.2,2.3,7,1.4])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["sparse","dense"]:
          for outputtype in ["sparse","dense"]:
            self.message("adj AD on SX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=SXFunction(self.sxinputs[inputshape][inputtype],self.sxoutputs[outputshape][outputtype])
            f.init()
            f.input().set(n)
            self.assertEqual(f.adjSeed().shape,f.output().shape,"adjSeed shape")
            self.assertEqual(f.adjSeed().size(),f.output().size(),"adjSeed shape")
            J = self.jacobians[inputtype][outputtype](*n)
            for d in [array([1,0,0,0]),array([0,2,0,0]),array([1.2,4.8,7.9,4.7])]:
              f.adjSeed().set(d)
              f.evaluate(0,1)
              seed = array(f.adjSeed()).ravel()
              sens = array(f.adjSens()).ravel()
              self.checkarray(sens,dot(J.T,seed),"AD")
              
  def test_SXevalSX(self):
    n=array([1.2,2.3,7,1.4])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            self.message("evalSX on SX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=SXFunction(self.sxinputs[inputshape][inputtype],self.sxoutputs[outputshape][outputtype])
            f.init()
            f.input().set(n)
            f.evaluate()
            r = DMatrix(f.output())
            J = self.jacobians[inputtype][outputtype](*n)
            
            seeds = [[1,0,0,0],[0,2,0,0],[1.2,4.8,7.9,4.6]]
            
            y = ssym("y",f.input().sparsity())
            
            fseeds = map(lambda x: DMatrix(f.input().sparsity(),x), seeds)
            aseeds = map(lambda x: DMatrix(f.output().sparsity(),x), seeds)
            res,fwdsens,adjsens = f.evalSX([y],map(lambda x: [x],fseeds),map(lambda x: [x],aseeds))
            fwdsens = map(lambda x: x[0],fwdsens)
            adjsens = map(lambda x: x[0],adjsens)
            
            fe = SXFunction([y],res)
            fe.init()
            
            fe.input().set(n)
            fe.evaluate()
            
            self.checkarray(r,fe.output())
            
            for sens,seed in zip(fwdsens,fseeds):
              fe = SXFunction([y],[sens])
              fe.input().set(n)
              fe.init()
              fe.evaluate()
              self.checkarray(c.flatten(fe.output()),mul(J,c.flatten(seed)),"AD") 

            for sens,seed in zip(adjsens,aseeds):
              fe = SXFunction([y],[sens])
              fe.input().set(n)
              fe.init()
              fe.evaluate()
              self.checkarray(c.flatten(fe.output()),mul(J.T,c.flatten(seed)),"AD") 

  def test_fwdMX(self):
    n=array([1.2,2.3,7,1.4])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            self.message("fwd AD on MX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=MXFunction(self.mxinputs[inputshape][inputtype],self.mxoutputs[outputshape][outputtype](self.mxinputs[inputshape][inputtype][0]))
            f.init()
            f.input().set(n)
            self.assertEqual(f.fwdSeed().shape,f.input().shape,"fwdSeed shape")
            self.assertEqual(f.fwdSeed().size(),f.input().size(),"fwdSeed shape")
            J = self.jacobians[inputtype][outputtype](*n)
            for d in [array([1,0,0,0]),array([0,2,0,0]),array([1.2,4.8,7.9,4.6])]:
              f.fwdSeed().set(d)
              f.evaluate(1,0)
              seed = array(f.fwdSeed()).ravel()
              sens = array(f.fwdSens()).ravel()
              self.checkarray(sens,dot(J,seed),"AD")    

  def test_adjMX(self):
    n=array([1.2,2.3,7,1.4])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            self.message("adj AD on MX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=MXFunction(self.mxinputs[inputshape][inputtype],self.mxoutputs[outputshape][outputtype](self.mxinputs[inputshape][inputtype][0]))
            f.init()
            f.input().set(n)
            self.assertEqual(f.adjSeed().shape,f.output().shape,"adjSeed shape")
            self.assertEqual(f.adjSeed().size(),f.output().size(),"adjSeed shape")
            J = self.jacobians[inputtype][outputtype](*n)
            for d in [array([1,0,0,0]),array([0,2,0,0]),array([1.2,4.8,7.9,4.3])]:
              f.adjSeed().set(d)
              f.evaluate(0,1)
              seed = array(f.adjSeed()).ravel()
              sens = array(f.adjSens()).ravel()
              self.checkarray(sens,dot(J.T,seed),"AD")
              
  def test_MXevalMX(self):
    n=array([1.2,2.3,7,1.4])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            self.message("evalMX on MX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=MXFunction(self.mxinputs[inputshape][inputtype],self.mxoutputs[outputshape][outputtype](self.mxinputs[inputshape][inputtype][0]))
            f.init()
            f.input().set(n)
            f.evaluate()
            r = DMatrix(f.output())
            J = self.jacobians[inputtype][outputtype](*n)
            
            seeds = [[1,0,0,0],[0,2,0,0],[1.2,4.8,7.9,4.6]]
            
            y = msym("y",f.input().sparsity())
            
            fseeds = map(lambda x: DMatrix(f.input().sparsity(),x), seeds)
            aseeds = map(lambda x: DMatrix(f.output().sparsity(),x), seeds)
            res,fwdsens,adjsens = f.evalMX([y],map(lambda x: [x],fseeds),map(lambda x: [x],aseeds))
            fwdsens = map(lambda x: x[0],fwdsens)
            adjsens = map(lambda x: x[0],adjsens)
            
            fe = MXFunction([y],res)
            fe.init()
            
            fe.input().set(n)
            fe.evaluate()
            
            self.checkarray(r,fe.output())
            
            for sens,seed in zip(fwdsens,fseeds):
              fe = MXFunction([y],[sens])
              fe.input().set(n)
              fe.init()
              fe.evaluate()
              self.checkarray(c.flatten(fe.output()),mul(J,c.flatten(seed)),"AD") 

            for sens,seed in zip(adjsens,aseeds):
              fe = MXFunction([y],[sens])
              fe.input().set(n)
              fe.init()
              fe.evaluate()
              self.checkarray(c.flatten(fe.output()),mul(J.T,c.flatten(seed)),"AD") 

  @known_bug()  # Not implemented
  def test_MXevalSX(self):
    n=array([1.2,2.3,7,1.4])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            self.message("evalSX on MX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=MXFunction(self.mxinputs[inputshape][inputtype],self.mxoutputs[outputshape][outputtype](self.mxinputs[inputshape][inputtype][0]))
            f.init()
            f.input().set(n)
            f.evaluate()
            r = DMatrix(f.output())
            J = self.jacobians[inputtype][outputtype](*n)
            
            seeds = [[1,0,0,0],[0,2,0,0],[1.2,4.8,7.9,4.6]]
            
            y = ssym("y",f.input().sparsity())
            
            fseeds = map(lambda x: DMatrix(f.input().sparsity(),x), seeds)
            aseeds = map(lambda x: DMatrix(f.output().sparsity(),x), seeds)
            res,fwdsens,adjsens = f.evalSX([y],map(lambda x: [x],fseeds),map(lambda x: [x],aseeds))
            fwdsens = map(lambda x: x[0],fwdsens)
            adjsens = map(lambda x: x[0],adjsens)
            
            fe = SXFunction([y],res)
            fe.init()
            
            fe.input().set(n)
            fe.evaluate()
            
            self.checkarray(r,fe.output())
            
            for sens,seed in zip(fwdsens,fseeds):
              fe = SXFunction([y],[sens])
              fe.input().set(n)
              fe.init()
              fe.evaluate()
              self.checkarray(c.flatten(fe.output()),mul(J,c.flatten(seed)),"AD") 

            for sens,seed in zip(adjsens,aseeds):
              fe = SXFunction([y],[sens])
              fe.input().set(n)
              fe.init()
              fe.evaluate()
              self.checkarray(c.flatten(fe.output()),mul(J.T,c.flatten(seed)),"AD")

  def test_MXevalSX_reduced(self):
    n=array([1.2,2.3,7,1.4])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            self.message("evalSX on MX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=MXFunction(self.mxinputs[inputshape][inputtype],self.mxoutputs[outputshape][outputtype](self.mxinputs[inputshape][inputtype][0]))
            f.init()
            f.input().set(n)
            f.evaluate()
            r = DMatrix(f.output())
  
            y = ssym("y",f.input().sparsity())
            
      
            res,fwdsens,adjsens = f.evalSX([y],[],[])
            
            fe = SXFunction([y],res)
            fe.init()
            
            fe.input().set(n)
            fe.evaluate()
            
            self.checkarray(r,fe.output())
                
  def test_Jacobian(self):
    n=array([1.2,2.3,7,4.6])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            for mode in ["forward","reverse"]:
              for numeric in [True,False]:
                self.message(" %s Jacobian on SX. Input %s %s, Output %s %s" % (mode,inputtype,inputshape,outputtype,outputshape) )
                f=SXFunction(self.sxinputs[inputshape][inputtype],self.sxoutputs[outputshape][outputtype])
                f.setOption("ad_mode",mode)
                f.setOption("numeric_jacobian",numeric)
                f.init()
                Jf=f.jacobian(0,0)
                Jf.init()
                Jf.input().set(n)
                Jf.evaluate()
                J = self.jacobians[inputtype][outputtype](*n)
                self.checkarray(array(Jf.output()),J,"Jacobian\n Mode: %s\n Input: %s %s\n Output: %s %s\n Numeric: %s"% (mode, inputshape, inputtype, outputshape, outputtype, numeric))
              
  def test_jacobianSX(self):
    n=array([1.2,2.3,7,4.6])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            self.message("jacobian on SX (SCT). Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            Jf=SXFunction(
              self.sxinputs[inputshape][inputtype],
              [
                  jacobian(
                    SXMatrix(self.sxoutputs[outputshape][outputtype][0]),
                    SXMatrix(self.sxinputs[inputshape][inputtype][0])
                  )
              ]
            )
            Jf.init()
            Jf.input().set(n)
            Jf.evaluate()
            J = self.jacobians[inputtype][outputtype](*n)
            self.checkarray(array(Jf.output()),J,"jacobian")
                          
  def test_jacsparsity(self):
    n=array([1.2,2.3,7,4.6])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            self.message("jacsparsity on SX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
            f=SXFunction(self.sxinputs[inputshape][inputtype],self.sxoutputs[outputshape][outputtype])
            f.init()
            J = self.jacobians[inputtype][outputtype](*n)
            self.checkarray(DMatrix(f.jacSparsity(),1),array(J!=0,int),"jacsparsity")
              
  @known_bug()
  def test_JacobianMX(self):
    n=array([1.2,2.3,7,4.6])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            for mode in ["forward","reverse"]:
              for numeric in [True,False]:
                self.message("adj AD on MX. Input %s %s, Output %s %s" % (inputtype,inputshape,outputtype,outputshape) )
                f=MXFunction(self.mxinputs[inputshape][inputtype],self.mxoutputs[outputshape][outputtype](self.mxinputs[inputshape][inputtype][0]))
                f.setOption("ad_mode",mode)
                f.setOption("numeric_jacobian",numeric)
                f.init()
                Jf=f.jacobian(0,0)
                Jf.init()
                Jf.input().set(n)
                Jf.evaluate()
                J = self.jacobians[inputtype][outputtype](*n)
                self.checkarray(Jf.output(),J,"Jacobian\n Mode: %s\n Input: %s %s\n Output: %s %s\n Numeric: %s"% (mode, inputshape, inputtype, outputshape, outputtype, numeric))
                   
  def test_jacsparsityMX(self):
    n=array([1.2,2.3,7,4.6])
    for inputshape in ["column","row","matrix"]:
      for outputshape in ["column","row","matrix"]:
        for inputtype in ["dense","sparse"]:
          for outputtype in ["dense","sparse"]:
            for mode in ["forward","reverse"]:
              self.message(" %s jacobian on MX (SCT). Input %s %s, Output %s %s" % (mode,inputtype,inputshape,outputtype,outputshape) )
              f=MXFunction(self.mxinputs[inputshape][inputtype],self.mxoutputs[outputshape][outputtype](self.mxinputs[inputshape][inputtype][0]))
              f.setOption("ad_mode",mode)
              f.init()
              Jf=f.jacobian(0,0)
              Jf.init()
              Jf.input().set(n)
              Jf.evaluate()
              J = self.jacobians[inputtype][outputtype](*n)
              self.checkarray(array(Jf.output()),J,"jacobian")
              self.checkarray(array(DMatrix(f.jacSparsity(),1)),array(J!=0,int),"jacsparsity")
              
     
              
  def test_hessian(self):
    self.message("Jacobian chaining")
    x=ssym("x")
    y=ssym("y")
    z=ssym("z")
    n=array([1.2,2.3,7])
    f=SXFunction([vertcat([x,y,z])],[vertcat([x+2*y**3+3*z**4])])
    f.setOption("numeric_jacobian",True)
    #f.setOption("ad_mode","forward")
    f.init()
    J=f.jacobian(0,0)
    J.init()
    m=MX("m",3,1)
    JT,_ = J.call([m])
    JT = MXFunction([m],[JT.T])
    #JT.setOption("ad_mode","reverse")
    JT.init()
    JT.input().set(n)
    JT.evaluate()
    H = JT.jacobian(0,0)
    H.init()
    H.input().set(n)
    #H.evaluate()
    
    #print array(JT.output())
    #print array(H.output())
    
  def test_bugshape(self):
    self.message("shape bug")
    x=ssym("x")
    y=ssym("y")

    inp=SXMatrix(5,1)
    inp[0,0]=x
    inp[3,0]=y

    f=SXFunction([inp],[vertcat([x+y,x,y])])
    #f.setOption("ad_mode","forward")
    f.setOption("numeric_jacobian",True)
    f.init()
    J=f.jacobian(0,0)
    J.init()
    J.input().set([2,7])
    J.evaluate()

    self.assertEqual(f.output().size1(),3,"Jacobian shape bug")
    self.assertEqual(f.output().size2(),1,"Jacobian shape bug")

    
  def test_bugglibc(self):
    self.message("Code that used to throw a glibc error")
    x=SX("x")
    y=SX("y")

    inp=SXMatrix(5,1)
    inp[0,0]=x
    inp[3,0]=y

    f=SXFunction([inp],[vertcat([x+y,x,y])])
    #f.setOption("ad_mode","forward")
    f.setOption("numeric_jacobian",True)
    f.init()
    J=f.jacobian(0,0)
    J.init()
    J.input().set([2,7])
    J.evaluate()

    f=SXFunction([inp],[vertcat([x+y,x,y])])
    f.setOption("numeric_jacobian",True)
    f.init()
    print f.input().shape
    J=f.jacobian(0,0)
    
    
  def test_MX(self):
    x = msym("x",2)
    y = msym("y",2,2)
    
    f1 = MXFunction([x,y],[x+y[0],mul(y,x)])
    f1.init()
    
    ndir = 2 # TODO: set back to 2 
    
    in1 = [x,y]
    v1 = [DMatrix([1.1,1.3]),DMatrix([[0.7,1.5],[2.1,0.9]])]
    
    w=x[:]
    w[1]*=2

    w2=x[:]
    w2[1]*=x[0]
    
    ww=x[:]
    ww[[0,1]]*=x

    wwf=x[:]
    wwf[[1,0]]*=x
    
    wwr=x[:]
    wwr[[0,0,1,1]]*=2
    
    yy=y[:,:]
    
    yy[:,0] = x

    yy2=y[:,:]
    
    yy2[:,0] = x**2
    
    yyy=y[:,:]
    
    yyy[[1,0],0] = x

    yyy2=y[:,:]
    
    yyy2[[1,0],0] = x**2
    
    
    # TODO: sparse seeding
    
    for inputs,values,out, jac, h in [
          (in1,v1,x,DMatrix.eye(2),0),
          (in1,v1,x.T,DMatrix.eye(2),0),
          (in1,v1,x**2,2*c.diag(x),0),
          (in1,v1,(x**2).T,2*c.diag(x),0),
          (in1,v1,c.reshape(x,(1,2)),DMatrix.eye(2),0),
          (in1,v1,c.reshape(x**2,(1,2)),2*c.diag(x),0),
          (in1,v1,x+y[0],DMatrix.eye(2),0),
          (in1,v1,x+x,2*DMatrix.eye(2),0),
          (in1,v1,x**2+x,2*c.diag(x)+DMatrix.eye(2),0),
          (in1,v1,x*x,2*c.diag(x),0),
          (in1,v1,x*y[0],DMatrix.eye(2)*y[0],0),
          (in1,v1,x[0],DMatrix.eye(2)[0,:],0),
          (in1,v1,(x**2)[0],horzcat([2*x[0],MX(1,1)]),0),
          #(in1,v1,x[0]+x[1],DMatrix.ones(1,2),0),  # knownbug #750
          (in1,v1,vertcat([x[1],x[0]]),sparse(DMatrix([[0,1],[1,0]])),0),
          (in1,v1,vertcat([x[1]**2,x[0]**2]),blockcat([[MX(1,1),2*x[1]],[2*x[0],MX(1,1)]]),0),
          (in1,v1,horzcat([x[1],x[0]]).T,sparse(DMatrix([[0,1],[1,0]])),0),
          (in1,v1,horzcat([x[1]**2,x[0]**2]).T,blockcat([[MX(1,1),2*x[1]],[2*x[0],MX(1,1)]]),0),
          (in1,v1,x[[0,1]],sparse(DMatrix([[1,0],[0,1]])),0),
          (in1,v1,(x**2)[[0,1]],2*c.diag(x),0),
          (in1,v1,x[[0,0,1,1]],sparse(DMatrix([[1,0],[1,0],[0,1],[0,1]])),0),
          (in1,v1,(x**2)[[0,0,1,1]],blockcat([[2*x[0],MX(1,1)],[2*x[0],MX(1,1)],[MX(1,1),2*x[1]],[MX(1,1),2*x[1]]]),0),
          #(in1,v1,wwr,sparse(DMatrix([[2,0],[0,2]])),0), # knownbug #748
          #(in1,v1,x[[1,0]],sparse(DMatrix([[0,1],[1,0]])),0), #  knownbug #746
          #(in1,v1,x[[1,0],0],sparse(DMatrix([[0,1],[1,0]])),0),
          (in1,v1,w,sparse(DMatrix([[1,0],[0,2]])),0),
          (in1,v1,w2,blockcat([[1,MX(1,1)],[x[1],x[0]]]),0),
          (in1,v1,ww,2*c.diag(x),0),
          #(in1,v1,wwf,2*c.diag(x[[1,0]]),0),
          (in1,v1,yy[:,0],DMatrix.eye(2),1), #knownbug #753
          (in1,v1,yy2[:,0],2*c.diag(x),1), #knownbug #753
          #(in1,v1,yyy[:,0],sparse(DMatrix([[0,1],[1,0]])),0),
          (in1,v1,mul(y,x),y,0),
          (in1,v1,mul(y,x**2),y*2*vertcat([x.T,x.T]),0),
          (in1,v1,sin(x),c.diag(cos(x)),0),
          (in1,v1,sin(x**2),c.diag(cos(x**2)*2*x),0),
          (in1,v1,x*y[:,0],c.diag(y[:,0]),0),
          #(in1,v1,x*y[[1,0],0],c.diag(y[[1,0],0]),0),
          (in1,v1,inner_prod(x,x),(2*x).T,0),
          (in1,v1,inner_prod(x**2,x),(3*x**2).T,0),
          #(in1,v1,c.det(horzcat([x,DMatrix([1,2])])),DMatrix([-1,2]),0), not implemented
          (in1,v1,f1.call(in1)[1],y,0),
          (in1,v1,f1.call([x**2,y])[1],y*2*vertcat([x.T,x.T]),0),
     ]:
      print out
      fun = MXFunction(inputs,[out,jac])
      fun.init()
      
      funsx = fun.expand()
      funsx.init()
      
      for i,v in enumerate(values):
        fun.input(i).set(v)
        funsx.input(i).set(v)
        
      fun.evaluate()
      funsx.evaluate()
      self.checkarray(fun.output(0),funsx.output(0))
      self.checkarray(fun.output(1),funsx.output(1))
      
      J_ = DMatrix(fun.output(1))
      
      def flatten(l):
        ret = []
        for i in l:
          ret.extend(i)
        return ret

      storage2 = []
      storage = []
      for f in [fun.expand(),fun]:
        f.setOption("number_of_adj_dir",ndir)
        f.setOption("number_of_fwd_dir",ndir)
        f.init()

        # Fwd and Adjoint AD
        for i,v in enumerate(values):
          f.input(i).set(v)
        
        
        for d in range(ndir):
          f.fwdSeed(0,d).set(DMatrix(inputs[0].sparsity(),random.random(inputs[0].size())))
          f.adjSeed(0,d).set(DMatrix(out.sparsity(),random.random(out.size())))
          f.fwdSeed(1,d).set(0)
          f.adjSeed(1,d).set(0)
          
        f.evaluate(ndir,ndir)
        for d in range(ndir):
          seed = array(f.fwdSeed(0,d)).ravel()
          sens = array(f.fwdSens(0,d)).ravel()
          self.checkarray(sens,mul(J_,seed),"Fwd %d %s" % (d,str(type(f))))

          seed = array(f.adjSeed(0,d)).ravel()
          sens = array(f.adjSens(0,d)).ravel()
          self.checkarray(sens,mul(J_.T,seed),"Adj %d" %d)
          
        # evalThings
        for sym, Function in [(msym,MXFunction),(ssym,SXFunction)]:
          if isinstance(f, MXFunction) and Function is SXFunction: continue
          if isinstance(f, SXFunction) and Function is MXFunction: continue
          
          
          def remove00(x):
            ret = DMatrix(x)
            ret[0,0] = DMatrix.sparse(1,1)
            return ret
            
          spmods = [lambda x: x , remove00]
          # dense
          for spmod,spmod2 in itertools.product(spmods,repeat=2):
            fseeds = [[sym("f",spmod(f.input(i)).sparsity()) for i in range(f.getNumInputs())]  for d in range(ndir)]
            aseeds = [[sym("a",spmod2(f.output(i)).sparsity())  for i in range(f.getNumOutputs())] for d in range(ndir)]
            inputss = [sym("i",f.input(i).sparsity()) for i in range(f.getNumInputs())]
        
            res,fwdsens,adjsens = f.eval(inputss,fseeds,aseeds)
            
            fseed = [DMatrix(fseeds[d][0].sparsity(),random.random(fseeds[d][0].size())) for d in range(ndir) ]
            aseed = [DMatrix(aseeds[d][0].sparsity(),random.random(aseeds[d][0].size())) for d in range(ndir) ]
            vf = Function(inputss+flatten([fseeds[i]+aseeds[i] for i in range(ndir)]),list(res) + flatten([list(fwdsens[i])+list(adjsens[i]) for i in range(ndir)]))
            
            vf.init()
            
            for i,v in enumerate(values):
              vf.input(i).set(v)
            offset = len(inputss)
              
            for d in range(ndir):
              vf.input(offset+0).set(fseed[d])
              for i in range(len(values)-1):
                vf.input(offset+i+1).set(0)
                
              offset += len(inputss)

              vf.input(offset+0).set(aseed[d])
              vf.input(offset+1).set(0)
              offset+=2
              
            assert(offset==vf.getNumInputs())
            
            vf.evaluate()
              
            offset = len(res)
            for d in range(ndir):
              seed = array(fseed[d]).ravel()
              sens = array(vf.output(offset+0)).ravel()
              offset+=len(inputss)
              self.checkarray(sens,mul(J_,seed),"eval Fwd %d %s" % (d,str(type(f))+str(sym)))

              seed = array(aseed[d]).ravel()
              sens = array(vf.output(offset+0)).ravel()
              offset+=len(inputss)
              
              self.checkarray(sens,mul(J_.T,seed),"eval Adj %d %s" % (d,str([vf.output(i) for i in range(vf.getNumOutputs())])))
          
          
            
          assert(offset==vf.getNumOutputs())
          
          # Complete dense random seeding
          random.seed(1)
          for i in range(vf.getNumInputs()):
            vf.input(i).set(DMatrix(vf.input(i).sparsity(),random.random(vf.input(i).size())))
          
          vf.evaluate()
          storage.append([DMatrix(vf.output(i)) for i in range(vf.getNumInputs())])
          
          # Second order sensitivities
          for sym2, Function2 in [(msym,MXFunction),(ssym,SXFunction)]:
          
            if isinstance(vf, MXFunction) and Function2 is SXFunction: continue
            if isinstance(vf, SXFunction) and Function2 is MXFunction: continue

            fseeds2 = [[sym2("f",vf.input(i).sparsity()) for i in range(vf.getNumInputs())] for d in range(ndir)]
            aseeds2 = [[sym2("a",vf.output(i).sparsity())  for i in range(vf.getNumOutputs()) ] for d in range(ndir)]
            inputss2 = [sym2("i",vf.input(i).sparsity()) for i in range(vf.getNumInputs())]
         
            if h==0:
              res2,fwdsens2,adjsens2 = vf.eval(inputss2,fseeds2,aseeds2)

              vf2 = Function(inputss2+flatten([fseeds2[i]+aseeds2[i] for i in range(ndir)]),list(res2) + flatten([list(fwdsens2[i])+list(adjsens2[i]) for i in range(ndir)]))
              vf2.init()
                
              random.seed(1)
              for i in range(vf2.getNumInputs()):
                vf2.input(i).set(DMatrix(vf2.input(i).sparsity(),random.random(vf2.input(i).size())))
              
              vf2.evaluate()
              storage2.append([DMatrix(vf2.output(i)) for i in range(vf2.getNumInputs())])
            else :
              #knownbug #753
              pass
            
        #  jacobian()
        for mode in ["forward","reverse"]:
          for numeric in [True,False]:
            f.setOption("ad_mode",mode)
            f.setOption("numeric_jacobian",numeric)
            f.init()
            Jf=f.jacobian(0,0)
            Jf.init()
            for i,v in enumerate(values):
              Jf.input(i).set(v)
            Jf.evaluate()
            self.checkarray(Jf.output(),J_)
            self.checkarray(DMatrix(Jf.output().sparsity(),1),DMatrix(J_.sparsity(),1),str(out)+str(mode)+str(numeric))
            self.checkarray(DMatrix(f.jacSparsity(),1),DMatrix(J_.sparsity(),1))
      
      # Remainder of second-order testing
      for st,order in [(storage,"first-order"),(storage2,"second-order")]:
        if order=="second-order": continue # knownbug #752
        if order=="first-order" and out is w2: continue #  knownbug #751
        for i in range(len(st)-1):
          for k,(a,b) in enumerate(zip(st[0],st[i+1])):
            if b.numel()==0 and sparse(a).size()==0: continue
            if a.numel()==0 and sparse(b).size()==0: continue
            self.checkarray(sparse(a),sparse(b),("%s, output(%d)" % (order,k))+str(vf2.input(0)))
      
            
      # Scalarized
      fun = MXFunction(inputs,[out[0],jac[0,:].T])
      fun.init()
      
      for i,v in enumerate(values):
        fun.input(i).set(v)
        
        
      fun.evaluate()
      J_ = DMatrix(fun.output(1))
      
      for f in [fun,fun.expand()]:
        #  gradient()
        for mode in ["forward","reverse"]:
          for numeric in [True,False]:
            f.setOption("ad_mode",mode)
            f.setOption("numeric_jacobian",numeric)
            f.init()
            Gf=f.gradient(0,0)
            Gf.init()
            for i,v in enumerate(values):
              Gf.input(i).set(v)
            Gf.evaluate()
            self.checkarray(Gf.output(),J_)
            #self.checkarray(DMatrix(Gf.output().sparsity(),1),DMatrix(J_.sparsity(),1),str(mode)+str(numeric)+str(out)+str(type(fun)))
        
    
    
if __name__ == '__main__':
    unittest.main()

