#include <bits/stdc++.h>
using namespace std;

int sumCheckPoints(int N, int S, string pos[], int val[])
// N is the number of checkpoints in the route, including the Starting point.
// S is the Starting point of the route.
// pos contains the relation between the Starting point and val.
// val contains the checkpoint at corresponding pos index.
{
    int sum=-1;

    // WRITE YOUR CODE HERE

    return sum;
}

int main()
{
    int N;
    cin>>N;
    int S;
    cin>>S;
    string str[N-1];
    int val[N-1];
    for(int i=0;i<N-1;i++)
    {
        cin>>str[i];
        cin>>val[i];
    }
    cout<<sumCheckPoints(N,S,str,val);
    return 0;
}
