# By: HurlSly
# Source: https://github.com/HurlSly/Python/blob/master/BitcoinECC.py
# Modified: random number generator in def GeneratePrivateKey(self):

import random
import hashlib
import os

class GaussInt:
    #A class for the Gauss integers of the form a + b sqrt(n) where a,b are integers.
    #n can be positive or negative.
    def __init__(self,x,y,n,p=0):
        if p:
            self.x=x%p
            self.y=y%p
            self.n=n%p
        else:
            self.x=x
            self.y=y
            self.n=n

        self.p=p
        
    def __add__(self,b):
        return GaussInt(self.x+b.x,self.y+b.y,self.n,self.p)
        
    def __sub__(self,b):
        return GaussInt(self.x-b.x,self.y-b.y,self.n,self.p)
    
    def __mul__(self,b):
        return GaussInt(self.x*b.x+self.n*self.y*b.y,self.x*b.y+self.y*b.x,self.n,self.p)
    
    def __div__(self,b):
        return GaussInt((self.x*b.x-self.n*self.y*b.y)/(b.x*b.x-self.n*b.y*b.y),(-self.x*b.y+self.y*b.x)/(b.x*b.x-self.n*b.y*b.y),self.n,self.p)
    
    def __eq__(self,b):
        return self.x==b.x and self.y==b.y
    
    def __repr__(self):
        if self.p:
            return "%s+%s (%d,%d)"%(self.x,self.y,self.n,self.p)
        else:
            return "%s+%s (%d)"%(self.x,self.y,self.n)
        
    def __pow__(self,n):
        b=Base(n,2)
        t=GaussInt(1,0,self.n)
        while b:
            t=t*t
            if b.pop():
                t=self*t
            
        return t

    def Inv(self):
        return GaussInt(self.x/(self.x*self.x-self.n*self.y*self.y),-self.y/(self.x*self.x-self.n*self.y*self.y),self.n,self.p)

def Cipolla(a,p):
    #Find a square root of a modulo p using the algorithm of Cipolla
    b=0
    while pow((b*b-a)%p,(p-1)/2,p)==1:
        b+=1

    return (GaussInt(b,1,b**2-a,p)**((p+1)/2)).x
    
def Base(n,b):
    #Decompose n in base b
    l=[]
    while n:
        l.append(n%b)
        n/=b

    return l
    
def InvMod(a,n):
    #Find the inverse mod n of a.
    #Use the Extended Euclides Algorithm.
    m=[]

    s=n
    while n:
        m.append(a/n)
        (a,n)=(n,a%n)

    u=1
    v=0
    while m:
        (u,v)=(v,u-m.pop()*v)

    return u%s

def b58encode(v):
    #Encode a byte string to the Base58
    digit="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    base=len(digit)
    val=0    
    for c in v:
        val*=256
        val+=ord(c)

    result=""
    while val:
        (val,mod)=divmod(val,base)
        result=digit[mod]+result

    pad=0
    for c in v:
        if c=="\0":
            pad+=1
        else:
            break

    return (digit[0]*pad)+result

def b58decode(v):
    #Decode a Base58 string to byte string
    digit="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    base=len(digit)
    val=0    
    for c in v:
        val*=base
        val+=digit.find(c)

    result=""
    while val:
        (val,mod)=divmod(val,256)
        result=chr(mod)+result

    pad=0
    for c in v:
        if c==digit[0]:
            pad+=1
        else:
            break

    result="\0"*pad+result

    return result

def Byte2Hex(b):
    #Convert a byte string to hex number
    out=""
    for x in b:
        y=hex(ord(x))[2:]
        if len(y)==1:
            y="0"+y
        out+="%2s"%y
    
    return out

def Int2Byte(n,b):
    #Convert a integer to a byte string of length b
    out=""
    
    for i in range(b):
        (n,m)=divmod(n,256)
        out=chr(m)+out
    
    return out

class EllipticCurvePoint:
    #Main class
    #It is an point on an Elliptic Curve
    
    def __init__(self,x,a,b,p,n=0):
        #We store the coordinate in x and the elliptic curbe parameter.
        #x is of length 3. This is the 3 projective coordinates of the point.
        self.x=x[:]
        self.a=a
        self.b=b
        self.p=p
        self.n=n

    def EqualProj(self,y):
        #Does y equals self ?
        #It computes self cross product with y and check if the result is 0.
        return self.x[0]*y.x[1]==self.x[1]*y.x[0] and self.x[1]*y.x[2]==self.x[2]*y.x[1] and self.x[2]*y.x[0]==self.x[0]*y.x[2]

    def __add__(self,y):
        #The main function to add self and y
        #It uses the formulas I derived in projective coordinates.
        #Projectives coordinates are more performant than the usual (x,y) coordinates
        #because it we don't need to compute inverse mod p, which is faster.
        z=EllipticCurvePoint([0,0,0],self.a,self.b,self.p)

        if self.EqualProj(y):
            d=(2*self.x[1]*self.x[2])%self.p
            d3=pow(d,3,self.p)
            n=(3*pow(self.x[0],2,self.p)+self.a*pow(self.x[2],2,self.p))%self.p
            
            z.x[0]=(pow(n,2,self.p)*d*self.x[2]-2*d3*self.x[0])%self.p
            z.x[1]=(3*self.x[0]*n*pow(d,2,self.p)-pow(n,3,self.p)*self.x[2]-self.x[1]*d3)%self.p
            z.x[2]=(self.x[2]*d3)%self.p
        else:
            d=(y.x[0]*self.x[2]-y.x[2]*self.x[0])%self.p
            d3=pow(d,3,self.p)
            n=(y.x[1]*self.x[2]-self.x[1]*y.x[2])%self.p

            z.x[0]=(y.x[2]*self.x[2]*pow(n,2,self.p)*d-d3*(y.x[2]*self.x[0]+y.x[0]*self.x[2]))%self.p
            z.x[1]=(pow(d,2,self.p)*n*(2*self.x[0]*y.x[2]+y.x[0]*self.x[2])-pow(n,3,self.p)*self.x[2]*y.x[2]-self.x[1]*d3*y.x[2])%self.p
            z.x[2]=(self.x[2]*d3*y.x[2])%self.p
        
        return z

    def __mul__(self,n):
        #The fast multiplication of point n times by itself.
        b=Base(n,2)
        t=EllipticCurvePoint(self.x,self.a,self.b,self.p)
        b.pop()
        while b:
            t+=t
            if b.pop():
                t+=self
                
        return t

    def __repr__(self):
        #print a point in (x,y) coordinate.
        return "x=%d\ny=%d\n"%((self.x[0]*InvMod(self.x[2],self.p))%self.p,(self.x[1]*InvMod(self.x[2],self.p))%self.p)
    
    def __eq__(self,x):
        #Does self==x ?
        return self.x==x.x and self.a==x.a and self.b==x.b and self.p==x.p
    
    def __ne__(self,x):
        #Does self!=x ?
        return self.x!=x.x or self.a!=x.a or self.b!=x.b or self.p!=x.p
    
    def Check(self):
        #Is self on the curve ?
        return (self.x[0]**3+self.a*self.x[0]*self.x[2]**2+self.b*self.x[2]**3-self.x[1]**2*self.x[2])%self.p==0

    def GeneratePrivateKey(self):
        #Generate a private key. It's just a random number between 1 and n-1.
        #Of course, this function isn't cryptographically secure.
        #Don't use it to generate your key. Use a cryptographically secure source of randomness instead.
        #self.d = random.randint(1,self.n-1)
        self.d = random.SystemRandom().randint(1,self.n-1) # Better random fix
    
    def SignECDSA(self,m):
        #Sign a message. The private key is self.d .
        h=hashlib.new("SHA256")
        h.update(m)
        z=int(h.hexdigest(),16)
        
        r=0
        s=0
        while not r or not s:
            #k=random.randint(1,self.n-1)
            k=random.SystemRandom().randint(1,self.n-1) # Better random fix
            R=self*k
            R.Normalize()
            r=R.x[0]%self.n
            s=(InvMod(k,self.n)*(z+r*self.d))%self.n

        return (r,s)
        
    def CheckECDSA(self,sig,m):
        #Check a signature (r,s) of the message m using the public key self.Q
        # and the generator which is self.
        #This is not the one used by Bitcoin because the public key isn't known;
        # only a hash of the public key is known. See the next function.
        (r,s)=sig        
        
        h=hashlib.new("SHA256")
        h.update(m)
        z=int(h.hexdigest(),16)
        
        if self.Q.x[2]==0:
            return False
        if not self.Q.Check():
            return False
        if (self.Q*self.n).x[2]!=0:
            return False
        if r<1 or r>self.n-1 or s<1 or s>self.n-1:
            return False

        w=InvMod(s,self.n)
        u1=(z*w)%self.n
        u2=(r*w)%self.n
        R=self*u1+self.Q*u2
        R.Normalize()

        return (R.x[0]-r)%self.n==0

    def VerifyMessageFromBitcoinAddress(self,adresse,m,sig):
        #Check a signature (r,s) for the message m signed by the Bitcoin 
        # address "addresse".
        h=hashlib.new("SHA256")
        h.update(m)
        z=int(h.hexdigest(),16)
        
        (r,s)=sig
        x=r
        y2=(pow(x,3,self.p)+self.a*x+self.b)%self.p
        y=Cipolla(y2,self.p)

        for i in range(2):
            kG=EllipticCurvePoint([x,y,1],self.a,self.b,self.p,self.n)  
            mzG=self*((-z)%self.n)
            self.Q=(kG*s+mzG)*InvMod(r,self.n)

            adr=self.BitcoinAddresFromPublicKey()
            if adr==adresse:
                break
            y=(-y)%self.p

        if adr!=adresse:
            return False

        return True

    def BitcoinAddressFromPrivate(self,pri=None):
        #Transform a private key in base58 encoding to a bitcoin address.
        #normal means "uncompressed".
        if not pri:
            print "Private Key :",
            pri=raw_input()

        normal=(len(pri)==51)
        pri=b58decode(pri)
        
        if normal:
            pri=pri[1:-4]
        else:
            pri=pri[1:-5]
        
        self.d=int(Byte2Hex(pri),16)
        
        return self.BitcoinAddress(normal)

    def PrivateEncoding(self,normal=True):
        #Encode a private key self.d to base58 encoding.
        p=Int2Byte(self.d,32)
        p="\80"+p
        
        if not normal:
            p+=chr(1)

        h=hashlib.new("SHA256")
        h.update(p)
        s=h.digest()
        
        h=hashlib.new("SHA256")
        h.update(s)
        s=h.digest()
        
        cs=s[:4]

        p+=cs
        p=b58encode(p)

        return p

    def BitcoinAddresFromPublicKey(self,normal=True):
        #Find the bitcoin address from the public key self.Q
        #We do normalization to go from the projective coordinates to the usual
        # (x,y) coordinates.
        self.Q.Normalize()
        if normal:
            pk=chr(4)+Int2Byte(self.Q.x[0],32)+Int2Byte((self.Q.x[1])%self.p,32)
        else:
            if self.Q.x[1]%2==0:
                pk=chr(2)+Int2Byte(self.Q.x[0],32)
            else:
                pk=chr(3)+Int2Byte(self.Q.x[0],32)
        
        version=chr(0)
        
        h=hashlib.new("SHA256")
        h.update(pk)
        s=h.digest()

        h=hashlib.new("RIPEMD160")
        h.update(s)
        kh=version+h.digest()

        h=hashlib.new("SHA256")
        h.update(kh)
        cs=h.digest()

        h=hashlib.new("SHA256")
        h.update(cs)
        cs=h.digest()[:4]

        adr=b58encode(kh+cs)

        return adr

    def BitcoinAddress(self,normal=True):
        #Computes a bitcoin address given the private key self.d.
        self.Q=self*self.d
        
        return self.BitcoinAddresFromPublicKey(normal)
    
    def BitcoinAddressGenerator(self,k,filename):
        #Generate Bitcoin address and write them in the filename in the multibit format.
        #Change the date as you like.
        f=open(filename,"w")
        for i in range(k):
            self.GeneratePrivateKey()
            adr=self.BitcoinAddress()
            p=self.PrivateEncoding()
            f.write("#%s\n%s 2014-01-30T12:00:00Z\n"%(adr,p))

            #print hex(self.d)
            print adr,p
        
        f.close()

    def TestSign(self):
        #Test signature
        self.GeneratePrivateKey()
        self.Q=self*self.d
        m="Hello World"
        adresse=self.BitcoinAddresFromPublicKey()
        (r,s)=self.SignECDSA(m)
        
        m="Hello World"
        print self.VerifyMessageFromBitcoinAddress(adresse,m,r,s)

    def Normalize(self):
        #Transform projective coordinates of self to the usual (x,y) coordinates.
        if self.x[2]:
            self.x[0]=(self.x[0]*InvMod(self.x[2],self.p))%self.p
            self.x[1]=(self.x[1]*InvMod(self.x[2],self.p))%self.p
            self.x[2]=1
        elif self.x[1]:
            self.x[0]=(self.x[0]*InvMod(self.x[1],self.p))%self.p
            self.x[1]=1
        elif self.x[0]:
            self.x[0]=1
        else:
            raise Exception

def Bitcoin():
    #Create the Bitcoin elliptiv curve
    a=0
    b=7
    p=2**256-2**32-2**9-2**8-2**7-2**6-2**4-1
    
    #Create the generator G of the Bitcoin elliptic curve, with is order n.
    Gx=int("79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",16)
    Gy=int("483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",16)
    n =int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",16)
    
    #Create the generator    
    return EllipticCurvePoint([Gx,Gy,1],a,b,p,n)


if __name__ == "__main__":
    bitcoin=Bitcoin()

    #Generate the public key from the private one
    print bitcoin.BitcoinAddressFromPrivate("23DKRBLkeDbcSaddsMYLAHXhanPmGwkWAhSPVGbspAkc72Hw9BdrDF")
    print bitcoin.BitcoinAddress()

    #Print the bitcoin address of the public key generated at the previous line
    adr=bitcoin.BitcoinAddresFromPublicKey()
    print adr

    #Sign a message with the current address
    m="Hello World"
    sig=bitcoin.SignECDSA("Hello World")
    #Verify the message using only the bitcoin adress, the signature and the message.
    #Not using the public key as it is not needed.
    print bitcoin.VerifyMessageFromBitcoinAddress(adr,m,sig)
